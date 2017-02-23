import boto3
import json
import os
import signal
import time

from ebcli.lib.aws import set_region, set_session_creds
from classes.tail_eb_environment import TailEBEnvironment
from util.aws_util import AWSConfig


class EBLogRetrievalService(object):

    def __init__(self, config, config_relative_dir_name, logger):
        self.config = config
        self.config_dir_name = config_relative_dir_name
        self.logger = logger

        self.attempt_previously_failed = False
        self.aws_config = AWSConfig(self.logger)
        self.credentials = {}
        self.environments_config = []
        self.environments_name = []
        self.is_sleeping = False
        self.job_name = config['job_name']
        self.local_backup_file_location = '{backup_dir}/{file_name}'
        self.missing_required_parameters = False
        self.shared_dictionary = {}
        self.sleeping_start_time = time.time()
        self.sleeping_window_in_seconds = 120
        self.target_arn = self.config['target_arn'] if 'target_arn' in self.config else False

        signal.signal(signal.SIGUSR1, self.load_eb_environments_config)

    def start_eb_log_retrieval_process(self):
        """
        Starts a constantly running process to tail logs from EB environments
        :return:
        """
        self.load_config()
        self.logger.info("Configuration dictionary loaded")
        self.logger.info("Starting constantly running process")

        while not (self.missing_required_parameters or self.attempt_previously_failed):
            try:
                if 'aws_access_key_id' in self.credentials and 'aws_secret_access_key' in self.credentials:
                    boto3.setup_default_session(**self.credentials)
                else:
                    boto3.setup_default_session(region_name=self.credentials['region_name'])

                eb_client = boto3.client('elasticbeanstalk')
                ec2_client = boto3.client('ec2')

                try:
                    with open(self.local_backup_file_location, 'r') as backup:
                        content = backup.read()
                        self.shared_dictionary = json.loads(content) if len(content) > 1 else {}
                        if not isinstance(self.shared_dictionary, dict): self.shared_dictionary = {}
                    self.logger.info("Shared dictionary from backup file restored")
                except FileNotFoundError:
                    pass

                for i, env_config in enumerate(self.environments_config):

                    if len(self.environments_config) != len(self.environments_name):
                        self.init_eb_environment(env_config)

                    eb_env = self.environments_name[i]

                    self.logger.info("Tailing the Elastic Beanstalk environment {eb_env}".format(eb_env=eb_env))
                    self.shared_dictionary[eb_env] = TailEBEnvironment(eb_env, eb_client, ec2_client,
                                                                       env_config, self.shared_dictionary[eb_env],
                                                                       self.logger).run()

                self.logger.info("All environments completed")
                self.logger.info(json.dumps(self.shared_dictionary, indent=4, sort_keys=True))

                with open(self.local_backup_file_location, 'w+') as backup:
                    backup.write(json.dumps(self.shared_dictionary, indent=4, sort_keys=True))

                if self.attempt_previously_failed:
                    message = "Logs successfully retrieved after unexpected exception"
                    self.logger.info("EB Tail Logs - {message}".format(message=message))
                    self.logger.info("SNS-Publishing the following message '{message}'".format(message=message))
                    self.aws_config.sns_publish(subject="EB Tail Logs", message=message, target_arn=self.target_arn)
                    self.attempt_previously_failed = False

                self.logger.info("Sleeping for {mins} min.".format(mins=float(self.sleeping_window_in_seconds/60)))
                self.is_sleeping = True
                self.sleeping_start_time = time.time()
                time.sleep(self.sleeping_window_in_seconds)
                self.is_sleeping = False

            except KeyError as e:
                self.logger.error("Please configure the {key} key or section in the config file".format(key=str(e)))
                self.missing_required_parameters = True
            except Exception as e:
                message = str(e)
                self.logger.error("Unexpected exception {message}".format(message=message))

                if not self.attempt_previously_failed:
                    self.logger.info("SNS-Publishing the following message '{message}'".format(message=message))
                    self.aws_config.sns_publish(subject="EB Log Retrieval Service - Unexpected exception caught", message=message, target_arn=self.target_arn)
                    self.attempt_previously_failed = True
                time.sleep(120)

        self.logger.info("constantly running process stopped")
        self.aws_config.sns_publish(subject="EB Log Retrieval Service", message="Constantly running process stopped", target_arn=self.target_arn)

    def load_config(self):
        """
        Loads the configuration parameters
        :return:
        """
        try:
            if 'sleeping_window_in_seconds' in self.config:
                self.sleeping_window_in_seconds = self.config['sleeping_window_in_seconds']
                self.logger.info("Sleeping window set to {sec} seconds".format(sec=self.sleeping_window_in_seconds))

            backup_file_name = self.config['backup_file_name']
            backup_directory = self.config['backup_directory']
            backup_directory = os.path.expanduser(backup_directory)
            self.logger.info("Backup directory set to {dir}".format(dir=backup_directory))
            self.local_backup_file_location = self.local_backup_file_location.format(backup_dir=backup_directory,
                                                                                     file_name=backup_file_name)
            self.load_credentials(self.config)
            self.load_environments(self.config)
        except KeyError as e:
            self.missing_required_parameters = True
            self.logger.error("Please configure the {key} key or section in the config file".format(key=str(e)))

    def load_credentials(self, config):
        """
        Loads AWS access key id, secret access key and region
        :param config:
        :return:
        """
        section = config['credentials']

        self.credentials['region_name'] = section['aws_region']
        # For future AWS API calls
        set_region(self.credentials['region_name'])

        if 'aws_access_key_id' in section and 'aws_secret_access_key' in section:
            self.credentials['aws_access_key_id'] = section['aws_access_key_id']
            self.credentials['aws_secret_access_key'] = section['aws_secret_access_key']
            set_session_creds(self.credentials['aws_access_key_id'], self.credentials['aws_secret_access_key'])

    def load_environments(self, config):
        """
        Loads environments configuration
        :param config:
        :return:
        """
        section = config['environments']

        for env in section:
            self.environments_config.append(env)

    def init_eb_environment(self, env_config):
        """
        Initializes one EB environment for the first time
        :param env_config:
        :return:
        """
        eb_env = ""

        if 'name' not in env_config and 'id' not in env_config:
            raise KeyError("Environment id and name have been omitted, please specify at least one")

        if 'id' in env_config:
            eb_env += env_config['id']

        if 'name' in env_config:
            eb_env = env_config['name']

        self.logger.info("Initialisation of {eb_env}".format(eb_env=eb_env))

        if 'key_pem' not in env_config:
            raise KeyError("Parameter 'key_pem' is not defined for environment {eb_env}".format(eb_env=eb_env))

        if 'files' not in env_config or ('files' in env_config and not isinstance(env_config['files'], list)):
            raise KeyError("Parameter 'files' is not defined for environment {eb_env}".format(eb_env=eb_env))

        self.environments_name.append(eb_env)
        self.shared_dictionary[eb_env] = {}

        return eb_env

    def load_eb_environments_config(self, signum, stack):
        """
        Dynamically update EB log retrieval configuration if the process is not currently running
        :param signum:
        :param stack:
        :return:
        """
        if signum == signal.SIGUSR1:
            if not self.is_sleeping:
                self.logger.info("Re-loading EB environments config is currently not possible")
            else:
                self.logger.info("Re-loads configuration file")
                cfg = {}
                with open(self.config_dir_name, 'r') as ymlfile:
                    yaml = __import__('yaml')
                    cfg = yaml.load(ymlfile)
                assert isinstance(cfg, dict)
                self.logger.info("Re-loads EB environments parameters")
                self.config = cfg
                self.environments_name = []
                self.environments_config = []
                self.load_environments(cfg)

                delta = time.time() - self.sleeping_start_time
                remaining_seconds = self.sleeping_window_in_seconds - delta
                self.logger.info("Will resume in {seconds}".format(seconds=round(float(remaining_seconds/60), 2)))
                time.sleep(remaining_seconds)
                self.is_sleeping = False
