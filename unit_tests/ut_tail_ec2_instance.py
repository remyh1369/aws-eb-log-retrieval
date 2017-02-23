import datetime
import json
import logging

from ebcli.lib.aws import set_region

from classes.tail_ec2_instance import TailEC2Instance


class TailEC2InstanceUT(object):

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

        self.files = [{"name":'/'.join([self.common_root, file]),
                       "rotated": False} for file in self.files]

    def test_tail_multiple_ec2_instances(self):
        key_pem_path = 'key_pem_file_path.pem'
        ec2_user = 'ec2-user'
        keep_files = True
        api_endpoint = None

        # Config EB environment 1
        eb_env_1 = 'your_eb_env_name'
        instance_id_1 = 'your_ec2_instance_id'
        host_1 = 'your_ec2_instance_host'
        instance_1_dict = {}
        environment_1_dict = {}

        # Config EB environment 2
        eb_env_2 = 'another_of_your_eb_env_name'
        instance_id_2 = 'another_of_your_ec2_instance_id'
        host_2 = 'another_of_your_ec2_instance_host'
        instance_2_dict = {}
        environment_2_dict = {}

        instance_1_dict = TailEC2Instance(eb_environment_id=eb_env_1, instance_id=instance_id_1,
                                    host=host_1, user=ec2_user, files=self.files,
                                    key_pem=key_pem_path, instance_dict=instance_1_dict,
                                    api_endpoint=api_endpoint, keep_files=keep_files, logger=logger).run()

        instance_2_dict = TailEC2Instance(eb_environment_id=eb_env_2, instance_id=instance_id_2,
                                    host=host_2, user=ec2_user, files=self.files,
                                    key_pem=key_pem_path, instance_dict=instance_2_dict,
                                    api_endpoint=api_endpoint, keep_files=keep_files, logger=logger).run()

        environment_1_dict.update({
            instance_id_1: instance_1_dict,
            'last_time_updated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

        environment_2_dict.update({
            instance_id_2: instance_2_dict,
            'last_time_updated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

        logger.info(json.dumps({eb_env_1: environment_1_dict}, indent=4, sort_keys=True))
        logger.info(json.dumps({eb_env_2: environment_2_dict}, indent=4, sort_keys=True))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('ut_test_tail_ec2_instance')
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('nose').setLevel(logging.WARNING)
    logging.getLogger('paramiko.transport').setLevel(logging.WARNING)

    set_region("us-east-1")
    test_tail_ec2_instance = TailEC2InstanceUT()

    logger.info("###### test_tail_multiple_ec2_instances #####")
    test_tail_ec2_instance.test_tail_multiple_ec2_instances()
