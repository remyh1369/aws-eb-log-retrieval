import os
import paramiko
import paramiko.config
import gzip

from datetime import datetime
from util.aws_util import format_aws_file
from paramiko.ssh_exception import SSHException

__author__ = 'rhuberdeau'


class GetLastRotatedLogs(object):

    def __init__(self, based_on_file, for_ec2_instance, from_ec2_host, with_user, destination_dir, key_pem_file=None, logger=None):
        self.rotated_path = 'rotated'
        self.ydm = datetime.now().strftime("%Y%d%m")
        self.dir_name = os.path.dirname(based_on_file)
        self.base_name = os.path.basename(based_on_file)
        self.instance_id = for_ec2_instance
        self.host = from_ec2_host
        self.user = with_user
        self.destination_dir = destination_dir
        self.key_pem_file = key_pem_file
        self.logger = logger

        self.ssh_cli = paramiko.SSHClient()
        self.ssh_cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_cli.load_system_host_keys()

        self.cd_command = "cd {dir_name}/{rotated_path}".format(dir_name=self.dir_name, rotated_path=self.rotated_path)
        self.ls_command = "ls -Artl {base_name}*gz".format(base_name=self.base_name)
        self.tail_command = "tail -n 1"
        self.grep_command = "grep -oe '{base_name}[0-9\-]*.gz$'".format(base_name=self.base_name)

        self.ls_tail_grep = " | ".join((self.ls_command, self.tail_command, self.grep_command))
        self.cd_ls_tail_grep = " && ".join((self.cd_command, self.ls_tail_grep))

    """
    Get the most recent archive containing all the logs from the previous rotation
    """
    def get_last_rotated_archive(self):
        last_rotated_archive = None
        try:
            self.ssh_cli.connect(self.host, username=self.user, key_filename=self.key_pem_file)
            self.logger.debug("Retrieving the most recent logs archive for {base_name} ...".format(base_name=self.base_name))
            self.logger.debug(self.cd_ls_tail_grep)
            stdin, stdout, stderr = self.ssh_cli.exec_command(self.cd_ls_tail_grep)

            error = stderr.readlines()
            output = stdout.readlines()

            if len(error) > 0:
                for line in error:
                    self.logger.error(line)

            if len(output) > 0:
                last_rotated_archive = output[0].replace("\n", "")
                self.logger.debug("Last archive {archive} ...".format(archive=last_rotated_archive))
            else: last_rotated_archive = "No rotated archive for {base_name}".format(base_name=self.base_name)

        except SSHException as e:
            self.logger.error("SSH exception while connecting to {host}: {err}".format(host=self.host, err=str(e)))
        finally:
            self.ssh_cli.close()

        return last_rotated_archive

    """
    Download the compressed archive locally
    """
    def copy_rotated_archive(self, last_rotated_archive):
        if last_rotated_archive != "":

            rotated_path_file = "{dir_name}/{rotated_path}/{rotated_archive}".format(dir_name=self.dir_name,
                                                                                     rotated_path=self.rotated_path,
                                                                                     rotated_archive=last_rotated_archive)

            base_file_name = format_aws_file(self.base_name, self.instance_id)
            local_path_file = "{dir}/{base_file_name}_{rotated}.gz".format(dir=self.destination_dir,
                                                                           base_file_name=base_file_name,
                                                                           rotated=self.rotated_path)
            try:
                self.logger.debug("Opening transport for SFTP transfer ...")
                private_key = paramiko.RSAKey.from_private_key_file(self.key_pem_file)
                transport = paramiko.Transport((self.host, paramiko.config.SSH_PORT))
                transport.connect(username=self.user, pkey=private_key)

                self.logger.debug("Copying {archive} from remote to local ...".format(archive=last_rotated_archive))
                sftp = paramiko.SFTPClient.from_transport(transport)
                sftp.get(rotated_path_file, local_path_file)

            except SSHException as e:
                local_path_file = False
                self.logger.error("SSH exception while copying {file} using SFTP: {err}".format(file=last_rotated_archive, err=str(e)))
            except Exception as e:
                local_path_file = False
                self.logger.error(str(e))
            finally:
                sftp.close()
                transport.close()

        return local_path_file

    """
    Get the most recent remote archive, download it and uncompress it
    """
    def get_rotated_file(self):
        # Get the archive name of the most recent rotated logs
        last_rotated_archive = self.get_last_rotated_archive()

        # Copy the archive remotely to locally
        local_path_archive = False
        if last_rotated_archive is not None and last_rotated_archive != '':
            local_path_archive = self.copy_rotated_archive(last_rotated_archive)

        # Uncompress the archive and remove it
        local_path_uncompressed_archive = False
        if local_path_archive is not False:

            with gzip.open(local_path_archive, 'rb') as gz:
                self.logger.debug("Uncompressing {archive} ...".format(archive=local_path_archive))
                bytes = gz.read()
                uncompressed_file_name = local_path_archive.replace('.gz', '')
                with open(uncompressed_file_name, 'wb') as file:
                    file.write(bytes)
                local_path_uncompressed_archive = uncompressed_file_name

            self.logger.debug("Removing {archive} ...".format(archive=local_path_archive))
            os.remove(local_path_archive)

        return local_path_uncompressed_archive
