import copy
import datetime

from botocore.parsers import ResponseParserError
from botocore.exceptions import ClientError, EndpointConnectionError

from classes.tail_ec2_instance import TailEC2Instance


class TailEBEnvironment(object):

    def __init__(self, eb_env_alias, eb_client, ec2_client, config, environment_dict, logger):

        # EB & EC2 clients
        self.eb_client = eb_client
        self.ec2_client = ec2_client

        # Config
        self.eb_env_alias = eb_env_alias
        self.environment_id = config['id'] if 'id' in config else ''
        self.environment_name = config['name'] if 'name' in config else ''

        self.key_pem = config['key_pem']
        self.files = config['files']
        self.keep_results_on_disk = config['keep_results_on_disk'] if 'keep_results_on_disk' in config else True
        self.user = config['user'] if 'user' in config else 'ec2-user'
        self.use_private_ip = config['use_private_ip'] if 'use_private_ip' in config else False
        self.api_endpoint = config['api_endpoint'] if 'api_endpoint' in config else None

        # EC2 host to tail logs
        self.hosts = {}

        # Dictionary of one EB environment to keep track of previously retrieved logs
        self.environment_dict = environment_dict

        self.logger = logger

    def find_instances(self):
        """
        Retrieves EC2 instance identifiers for the given EB environment
        :return:
        """
        eb_env_args = {}
        if len(self.environment_name) >= 4:
            eb_env_args["EnvironmentName"] = self.environment_name
        if self.environment_id != '':
            eb_env_args["EnvironmentId"] = self.environment_id

        try:
            responses = self.eb_client.describe_environment_resources(**eb_env_args)
            resources = responses['EnvironmentResources']
            for instance in resources['Instances']:
                self.hosts[instance['Id']] = {}
                self.logger.info("{eb_env}: Found instance {instance}".format(eb_env= self.eb_env_alias, instance=instance['Id']))
        except EndpointConnectionError as e:
            raise e

    def find_ec2_instance_hosts(self):
        """
        Looks for EC2 instance hosts based on the EC2 identifiers retrieved
        :return:
        """
        try:
            responses = self.ec2_client.describe_instances(InstanceIds=list(self.hosts.keys()))
            for reservation in responses['Reservations']:
                for instance in reservation['Instances']:
                    ip = instance['PrivateIpAddress'] if self.use_private_ip else instance['PublicIpAddress']
                    self.logger.info("{eb_env}: Found host {ip} for instance {instance}".format(eb_env=self.eb_env_alias, ip=ip, instance=instance['InstanceId']))
                    self.hosts[instance['InstanceId']] = ip
        except ClientError as e:
            raise e
        except EndpointConnectionError as e:
            raise e

    def tail_ec2_hosts(self):
        """
        Tails logs of each EC2 host listed for this EN environment
        :return:
        """
        for instance_id in self.hosts.keys():

            if instance_id not in self.environment_dict.keys():
                self.environment_dict[instance_id] = {}

            self.environment_dict[instance_id] = TailEC2Instance(self.eb_env_alias, instance_id, self.hosts[instance_id],
                                                                 self.user, self.files, self.key_pem,
                                                                 self.environment_dict[instance_id], self.api_endpoint,
                                                                 self.keep_results_on_disk, self.logger).run()

    def run(self):
        """
        Orchestrates the tailing logs process for one EB environment
        :return:
        """
        try:
            self.logger.info("{eb_env}: Finding EC2 instances ...".format(eb_env=self.eb_env_alias))
            self.find_instances()

            self.logger.info("{eb_env}: Retrieving EC2 instance hosts ...".format(eb_env=self.eb_env_alias))
            self.find_ec2_instance_hosts()

            self.logger.info("{eb_env}: Tailing logs from EC2 hosts ...".format(eb_env=self.eb_env_alias))
            self.tail_ec2_hosts()

            self.logger.info("{eb_env}: Tailing logs completed".format(eb_env=self.eb_env_alias))

            # Add last date time updated
            self.environment_dict['last_time_updated'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Updating dictionary of this EB environment to remove EC2 instances keys that don't exist anymore
            eb_dict_copy = copy.deepcopy(self.environment_dict)
            for ec2_instance_key in list(eb_dict_copy):
                if ec2_instance_key not in self.hosts.keys():
                    self.environment_dict.pop(ec2_instance_key, None)

        except ResponseParserError as e:
            self.logger.error("{eb_env}: {error}".format(eb_env=self.eb_env_alias, error=str(e)))
            self.logger.info("{eb_env}: Expected to be fixed in botocore 1.4.53".format(eb_env=self.eb_env_alias))
        except ClientError as e:
            message = str(e)
            if 'Error' in e.response and 'Message' in e.response['Error']:
                message = e.response['Error']['Message']

            self.logger.error("{eb_env}: {error}".format(eb_env=self.eb_env_alias, error=message))
        except EndpointConnectionError as e:
            self.logger.error("{eb_env}: {error}".format(eb_env=self.eb_env_alias, error=str(e)))
        except Exception as e:
            self.logger.error("{eb_env}: Type ({type}) - Error ({error})".format(eb_env=self.eb_env_alias, type=type(e), error=str(e)))
        finally:
            return self.environment_dict
