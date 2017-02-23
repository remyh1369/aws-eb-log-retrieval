import boto3
import copy
import json
import logging

from ebcli.lib.aws import set_region

from classes.tail_eb_environment import TailEBEnvironment


class TailEBEnvironmentUT(object):

    def __init__(self):
        # Log files to retrieve from EC2 instances
        self.common_root = "/var/log"
        self.files = [
            "httpd/elasticbeanstalk-access_log",
            "httpd/error_log",
            "tomcat7/catalina.out",
            "tomcat7/localhost_access_log.txt",
            "httpd/access_log"
        ]

        self.files = [{"name": '/'.join([self.common_root, file]),
                       "rotated": False} for file in self.files]

        # EB and EC2 clients
        self.eb_client = boto3.client('elasticbeanstalk')
        self.ec2_client = boto3.client('ec2')

        self.api_endpoint = None
        self.key_pem = 'key_pem_file_path'
        self.ec2_user = 'ec2-user'
        self.environment_1_dict = {}
        self.environment_2_dict = {}
        self.environment_3_dict = {}


    def test_find_instances_by_eb_name(self):
        try:
            config = {'name': 'your_eb_env_name_or_id', 'key_pem': '', 'files': []}
            eb_env = TailEBEnvironment("eb_env_alias_1", self.eb_client, self.ec2_client, config, {}, logger)
            eb_env.find_instances()

            config = {'name': 'another_of_your_eb_env_name_or_id', 'key_pem': '', 'files': []}
            eb_env = TailEBEnvironment("eb_env_alias_2", self.eb_client, self.ec2_client, config, {}, logger)
            eb_env.find_instances()

            config = {'name': 'another_of_your_eb_env_name_or_id', 'key_pem': '', 'files': []}
            eb_env = TailEBEnvironment("eb_env_alias_3", self.eb_client, self.ec2_client, config, {}, logger)
            eb_env.find_instances()
        except Exception as e:
            logger.error(str(e))

    def test_find_instances_by_eb_id(self):
        try:
            config = {'id': 'your_eb_env_id', 'key_pem': '', 'files': []}
            eb_env = TailEBEnvironment("eb_env_alias_1", self.eb_client, self.ec2_client, config, {}, logger)
            eb_env.find_instances()
        except Exception as e:
            logger.error(str(e))

    def test_find_ec2_hosts(self):
        try:
            config = {'name': 'your_eb_env_name', 'key_pem': '', 'files': []}
            env = TailEBEnvironment("eb_env_alias_1", self.eb_client, self.ec2_client, config, {}, logger)
            env.find_instances()
            env.find_ec2_instance_hosts()
        except Exception as e:
            logger.error(str(e))

    def test_tail_multiple_eb_environments(self):
        config1 = {'name': 'your_eb_env_name',
                             'key_pem': self.key_pem,
                             'files': self.files,
                             'api_endpoint': None,
                             'user': self.ec2_user}

        # Copy config EB1, to replace if you want a specific config
        config2 = copy.deepcopy(config1)
        config2['name'] = 'another_of_your_eb_env_name'

        # Copy config EB1, to replace if you want a specific config
        config3 = copy.deepcopy(config1)
        config3['name'] = 'another_of_your_eb_env_name'

        self.environment_1_dict = TailEBEnvironment(eb_env_alias=config1['name'], eb_client=self.eb_client,
                                                    ec2_client=self.ec2_client, config=config1,
                                                    environment_dict=self.environment_1_dict, logger=logger).run()

        self.environment_2_dict = TailEBEnvironment(eb_env_alias=config2['name'], eb_client=self.eb_client,
                                                    ec2_client=self.ec2_client, config=config2,
                                                    environment_dict=self.environment_2_dict, logger=logger).run()

        self.environment_3_dict = TailEBEnvironment(eb_env_alias=config3['name'], eb_client=self.eb_client,
                                                    ec2_client=self.ec2_client, config=config3,
                                                    environment_dict=self.environment_3_dict, logger=logger).run()

        logger.info(json.dumps({config1['name']: self.environment_1_dict}, indent=4, sort_keys=True))
        logger.info(json.dumps({config2['name']: self.environment_2_dict}, indent=4, sort_keys=True))
        logger.info(json.dumps({config3['name']: self.environment_3_dict}, indent=4, sort_keys=True))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('ut_test_tail_ec2_instance')
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('nose').setLevel(logging.WARNING)
    logging.getLogger('paramiko.transport').setLevel(logging.WARNING)

    set_region("us-east-1")
    test_tail_eb_env = TailEBEnvironmentUT()

    logger.info("###### TEST FIND INSTANCES BY EB ENV NAME #####")
    test_tail_eb_env.test_find_instances_by_eb_name()

    logger.info("###### TEST FIND INSTANCES BY EB ENV ID #####")
    test_tail_eb_env.test_find_instances_by_eb_id()

    logger.info("###### TEST FIND EC2 HOSTS #####")
    test_tail_eb_env.test_find_ec2_hosts()

    logger.info("###### TEST TAIL MULTIPLE EB ENVIRONMENTS #####")
    test_tail_eb_env.test_tail_multiple_eb_environments()