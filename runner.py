import logging
import os
import sys

import yaml

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('AWS_EB_Log_Retrieval')

from classes.aws_eb_log_retrieval_service import EBLogRetrievalService

if __name__ == "__main__":
    try:
        yaml_config_file_path = sys.argv[1]
        config_dir_name = os.path.dirname(yaml_config_file_path)
        logger.info('Relative directory name is {dir_name}'.format(dir_name=config_dir_name))

        try:
            with open(yaml_config_file_path, 'r') as yml_file:
                config_dict = yaml.load(yml_file)
            assert isinstance(config_dict, dict)

            logger.debug(config_dict)
            EBLogRetrievalService(config=config_dict, config_relative_dir_name=config_dir_name,
                                  logger=logger).start_eb_log_retrieval_process()
        except AssertionError:
            logger.error("{filename}: configuration file content should be a dict".format(filename=path))
        except FileNotFoundError:
            logger.error("Configuration file {filename} does not exist".format(filename=path))
    except IndexError:
        logger.debug("Usage is: python3 -m runner path/to/config/file.yml")