import os
import paramiko
import queue

from botocore.exceptions import EndpointConnectionError
from ebcli.objects.exceptions import NoRegionError
from ebcli.objects.exceptions import ServiceError
from os.path import expanduser
from paramiko.ssh_exception import SSHException
from threading import Thread
from queue import Empty

from util.aws_util import authorize_ssh, revoke_ssh_authorization, format_aws_file
from util.curl_util import curl_post_data
from classes.get_last_rotated_logs import GetLastRotatedLogs


class TailEC2Instance(object):

    def __init__(self, eb_environment_id, instance_id, host, user, files, key_pem,
                 instance_dict, api_endpoint=None, keep_files=True, logger=None):

        self.eb_environment_id = eb_environment_id
        self.instance_id = instance_id
        self.host = host
        self.user = user
        self.files = files

        if os.path.basename(key_pem) == key_pem:
            sep = os.path.sep
            p = '~' + sep + '.ssh' + sep
            p = expanduser(p)
            self.key_pem_path = p + key_pem
        else:
            self.key_pem_path = key_pem

        self.instance_dict = instance_dict
        self.api_endpoint = api_endpoint
        self.keep_files = keep_files
        self.logger = logger

        # SSH-specific variables
        self.threads = []
        self.queue = queue.Queue()
        self.responses = []
        self.group = None

    def run(self):
        """
        Orchestrates a single EC2 instance log tailing process
            - loads the dictionary of files
            - grant an SSH connection into the EC2 instance if needed
            - collects the regular log files (and the rotated ones if needed) and saves them locally
            - sends the logs to a third-party platform if set
            - clears all saved log files if set and revokes the SSH authorization
            - updates the instance dictionary with the updated number of lines
        :return:
        """
        try:
            # Checks if log file path  exist in instance_dictionary
            for file in self.files:
                if file['name'] not in self.instance_dict:
                    self.instance_dict[file['name']] = {}

            # Pre-Tail step
            self.group = authorize_ssh(self.instance_id, self.logger)

            # Part 1: Tail regular log files and, if enabled, rotated ones from archives
            regular_files = self.tail_regular_logs()
            rotated_files = self.tail_rotated_logs()

            # Part 2 (optional): Send logs to a third-party platform
            if self.api_endpoint is not None: self.send_log_files(regular_files + rotated_files)

            # Part 3 (optional): Clear saved files of logs
            if not self.keep_files: self.clear_log_files(regular_files + rotated_files)

            # Post-Tail step
            revoke_ssh_authorization(self.instance_id, self.group, self.logger)

            self.logger.info("{instance}: Tailing logs completed".format(instance=self.instance_id))
        except KeyError as e:
            self.logger.error("{instance}: {error}".format(instance=self.instance_id, error=str(e)))
        except NoRegionError:
            self.logger.error("{instance}: region should be specified with 'ebcli.classes.aws.set_region'".format(instance=self.instance_id))
        except EndpointConnectionError as e:
            self.logger.error("{instance}: {error}".format(instance=self.instance_id, error=str(e)))
        except ServiceError as e:
            self.logger.error("{instance}: code ({code}),  message({message})".format(instance=self.instance_id, code=e.code, message=str(e)))
        except Exception as e:
            self.logger.error("{instance}: {error}".format(instance=self.instance_id, error=str(e)))
        finally:
            return self.instance_dict

    def tail_regular_logs(self):
        """
        Tails and saves the remotely regular log files
        :return:
        """
        try:
            commands = []

            self.logger.debug("{instance}: SSH into instance and tail logs".format(instance=self.instance_id))
            for file in self.files:
                commands.append("tail --lines=+0 {log_file}".format(log_file=file['name']))

            for i, cmd in enumerate(commands):
                thread = Thread(target=self.ssh_exec_command, args=(cmd, self.files[i]['name'], self.queue))
                thread.start()
                self.threads.append(thread)

            for thread in self.threads:
                thread.join()

            while True:
                self.responses.append(self.queue.get(False))
        except Empty as e:
            self.logger.debug("{instance}: Queue emptied".format(instance=self.instance_id))
            return self.save_regular_log_files()
        except Exception as e:
            self.logger.error("{instance}: Error type ({type})".format(instance=self.instance_id, type=type(e)))
            self.logger.error("{instance}: Error ({error})".format(instance=self.instance_id, error=str(e)))
            raise e

    def tail_rotated_logs(self):
        """
        Collects the logs from the most recent archive if a rotation happened
        :return:
        """
        rotated_files = []

        for response in self.responses:
            output = response['output']
            filename = response['file']
            new_nb_lines = len(output)

            rotated = [file['rotated'] for file in self.files if file['name'] == filename][0]

            try:
                # The number of lines might have never been set yet
                if 'nb_lines' in self.instance_dict[filename]:
                    old_nb_lines = self.instance_dict[filename]['nb_lines']

                    # If already set, we have to know whether or not we are facing a log rotation
                    if rotated and old_nb_lines > new_nb_lines:
                        rotated_file_name = self.save_rotated_log_files(filename, old_nb_lines)
                        if rotated_file_name is not False:
                            rotated_files.append(rotated_file_name)

                # We want to update the regular log file whether or not it's empty
                self.instance_dict[filename]['nb_lines'] = new_nb_lines

            except Exception as e:
                self.logger.error("{instance}: Exception when updating instance dictionary, {err}".format(instance=self.instance_id, err=str(e)))
                raise e

        return rotated_files

    def save_rotated_log_files(self, filename, old_nb_lines):
        """
        Saves one rotated log file from its last rotated archive
        :param filename:
        :param old_nb_lines:
        :return:
        """
        self.logger.debug("{instance} retrieving the most recent archive for {filename}".format(instance=self.instance_id, filename=filename))

        # Instantiate LastRotatedLogs to retrieve the most recent archive and copy it locally
        local_rotated_file = GetLastRotatedLogs(filename, self.instance_id, self.host, self.user,
                                             os.curdir, self.key_pem_path, self.logger).get_rotated_file()

        # We just want the logs we haven't previously processed
        if local_rotated_file is not False:
            lines = open(local_rotated_file).readlines()
            len_rotated_archive = len(lines)
            difference = len_rotated_archive - old_nb_lines

            if difference > 0:
                self.logger.debug("{instance}: {old_nb_lines} logs previously retrieved in {filename}".format(instance=self.instance_id, old_nb_lines=old_nb_lines, filename=filename))
                self.logger.debug("{instance}: keeping {diff} new logs for {filename}".format(instance=self.instance_id, diff=difference, filename=filename))
                with open(local_rotated_file, 'w') as rotated_logs:
                    for log in lines[old_nb_lines:len_rotated_archive]:
                        formatted_log = "[{eb_env}] - {log}".format(eb_env=self.eb_environment_id, log=log)
                        rotated_logs.write(formatted_log)
            else:
                os.remove(local_rotated_file)
                local_rotated_file = False
        else:
            self.logger.error("{instance}: failed to get the rotated archive for {file}".format(instance=self.instance_id, file=filename))
        return local_rotated_file

    def save_regular_log_files(self):
        """
        Saves regular log files whether or not the given outputs contain rows
        Automatically take into consideration new logs and skips ones previously processed
        :return:
        """
        self.logger.debug("{instance}: Saving logs into disk".format(instance=self.instance_id))
        files = []
        for response in self.responses:

            file_name = format_aws_file(os.path.basename(response['file']), self.instance_id)
            file = response['file']
            old_nb_lines = self.instance_dict[file]['nb_lines'] if 'nb_lines' in self.instance_dict[file] else 0
            output = response['output']
            output = output[old_nb_lines:len(output)]
            error = response['error']

            difference = len(output)
            self.instance_dict[file]['nb_lines'] = old_nb_lines + difference

            if len(error) > 0:
                self.logger.error("{instance}: Errors in response during SSH, {error}".format(instance=self.instance_id, error=error))
            if difference == 0: continue

            with open(file_name, 'w') as log_file:
                for log in output:
                    formatted_log = "[{eb_env}] - {log}".format(eb_env=self.eb_environment_id, log=log)
                    log_file.write(formatted_log)
                files.append(file_name)
                self.logger.debug("{instance}: {nb} new logs saved for {file}".format(instance=self.instance_id, nb=difference, file=file_name))
        return files

    def send_log_files(self, files):
        """
        Sends logs from the saved files to a third-party platform through an endpoint
        :param files:
        :return:
        """
        self.logger.debug("{instance}: send logs to a third-party platform".format(instance=self.instance_id))
        for file_name in files:
            self.logger.debug("{instance}: using {api_endpoint} endpoint to perform curl".format(instance=self.instance_id, api_endpoint=self.api_endpoint))
            self.logger.debug("{instance}: post log file {file_name}".format(instance=self.instance_id, file_name=file_name))
            curl_post_data(self.api_endpoint, file_name, self.logger)

    def clear_log_files(self, files):
        """
        Clears the previously saved log files (the regular and the rotated ones)
        :param files:
        :return:
        """
        if len(files) > 0:
            self.logger.info("{instance}: Clearing saved logs".format(instance=self.instance_id))
        else:
            self.logger.info("{instance}: Nothing to clear".format(instance=self.instance_id))

        for file_name in files:
            os.remove(file_name)
            self.logger.info("{instance}: {file} removed from local disk".format(instance=self.instance_id, file=file_name))

    def ssh_exec_command(self, cmd, filename, queue):
        """
        Executes command for a specific log file with its own SSH client
        :param cmd:
        :param filename:
        :param queue:
        :return:
        """
        ssh_cli = paramiko.SSHClient()
        ssh_cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_cli.load_system_host_keys()
        try:
            ssh_cli.connect(hostname=self.host, username=self.user, key_filename=self.key_pem_path)
            stdin, stdout, stderr = ssh_cli.exec_command(cmd)
            self.logger.debug("{instance}: Executing {cmd} through SSH".format(instance=self.instance_id, cmd=cmd))
            out = stdout.readlines()
            err = stderr.readlines()
            queue.put({"file": filename, "output": out, "error": err})
        except SSHException as e:
            self.logger.error("{instance}: ssh exception says {error} ".format(instance=self.instance_id, error=str(e)))
        except FileNotFoundError:
            self.logger.error("{instance}: {key_pem} pem file not found".format(instance=self.instance_id, key_pem=self.key_pem_path))
        except Exception as e:
            self.logger.error("{instance}: ssh_exec_command - {type}".format(instance=self.instance_id, type=type(e)))
            self.logger.error("{instance}: ssh_exec_command - {error} ".format(instance=self.instance_id, error=str(e)))
        finally:
            ssh_cli.close()
