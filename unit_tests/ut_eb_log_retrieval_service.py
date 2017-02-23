import logging

from ebcli.lib.aws import set_region

from classes.aws_eb_log_retrieval_service import EBLogRetrievalService


class EBLogRetrievalServiceUT(object):

    def __init__(self):
        self.config = {
            "job_name": "aws-eb-log-retrieval",
            "sleeping_window_in_seconds": 30,
            "backup_file_name": "aws_eb_log_retrieval_backup",
            "backup_directory": "~/",
            "credentials": {
                "aws_region": "us-east-1"
            },
            "environments": [
                {
                    "name": "your_eb_env_name_or_id",
                    "files": [
                        {"name": "/var/log/httpd/elasticbeanstalk-access_log", "rotated": False},
                        {"name": "/var/log/httpd/error_log", "rotated": False},
                        {"name": "/var/log/tomcat7/catalina.out", "rotated": False},
                        {"name": "/var/log/tomcat7/localhost_access_log.txt", "rotated": False},
                        {"name": "/var/log/httpd/access_log", "rotated": False}
                    ],
                    "key_pem": "key_pem_file_path.pem"
                },
                {
                    "name": "another_of_your_eb_env_name_or_id",
                    "files": [
                        {"name": "/var/log/httpd/elasticbeanstalk-access_log", "rotated": False},
                        {"name": "/var/log/httpd/error_log", "rotated": False},
                        {"name": "/var/log/tomcat7/catalina.out", "rotated": False},
                        {"name": "/var/log/tomcat7/localhost_access_log.txt", "rotated": False},
                        {"name": "/var/log/httpd/access_log", "rotated": False}
                    ],
                    "key_pem": "key_pem_file_path.pem"
                },
                {
                    "name": "another_of_your_eb_env_name_or_id",
                    "files": [
                        {"name": "/var/log/httpd/elasticbeanstalk-access_log", "rotated": False},
                        {"name": "/var/log/httpd/error_log", "rotated": False},
                        {"name": "/var/log/tomcat7/catalina.out", "rotated": False},
                        {"name": "/var/log/tomcat7/localhost_access_log.txt", "rotated": False},
                        {"name": "/var/log/httpd/access_log", "rotated": False}
                    ],
                    "key_pem": "key_pem_file_path.pem"
                },
                {
                    "name": "another_of_your_eb_env_name_or_id",
                    "files": [
                        {"name": "/var/log/httpd/elasticbeanstalk-access_log", "rotated": False},
                        {"name": "/var/log/httpd/error_log", "rotated": False},
                        {"name": "/var/log/tomcat7/catalina.out", "rotated": False},
                        {"name": "/var/log/tomcat7/localhost_access_log.txt", "rotated": False},
                        {"name": "/var/log/httpd/access_log", "rotated": False}
                    ],
                    "key_pem": "key_pem_file_path.pem"
                }
            ]
        }

    def unit_test_eb_log_retrieval_service(self):
        test_eb_log_retrieval_service = EBLogRetrievalService(config=self.config,
                                                              config_relative_dir_name='config',
                                                              logger=logger)
        test_eb_log_retrieval_service.start_eb_log_retrieval_process()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('ut_test_tail_ec2_instance')
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('nose').setLevel(logging.WARNING)
    logging.getLogger('paramiko.transport').setLevel(logging.WARNING)

    set_region("us-east-1")
    test_eb_log_retrieval_service = EBLogRetrievalServiceUT()
    test_eb_log_retrieval_service.unit_test_eb_log_retrieval_service()
