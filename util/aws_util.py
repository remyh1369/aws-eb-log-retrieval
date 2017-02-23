import boto.sns

from datetime import datetime
from ebcli.lib import ec2


class AWSConfig(object):
    def __init__(self, logger):
        super(AWSConfig, self).__init__()
        self.access_key_id = boto.config.get_value('Credentials', 'aws_access_key_id')
        self.secret_key = boto.config.get_value('Credentials', 'aws_secret_access_key')
        self.logger = logger

    def sns_publish(self, subject, message, target_arn):
        try:
            sns = boto.sns.SNSConnection()
            sns.publish(target_arn=target_arn, subject=subject, message=message)
            return sns
        except Exception as e:
            self.logger.error("Failed to connect or publish SNS message: {message} "
                              "because of the following error: {error}".format(message=message, error=str(e)))

# Opens port 22 to allow SSH connection into the given EC2 instance
def authorize_ssh(ec2_instance_id, logger):
    instance = ec2.describe_instance(ec2_instance_id)
    security_groups = instance['SecurityGroups']

    ssh_group = ''
    group_id = ''

    for group in security_groups:
        group_id = group['GroupId']
        # see if group has ssh rule
        group = ec2.describe_security_group(group_id)
        for permission in group.get('IpPermissions', []):
            if permission.get('ToPort', None) == 22:
                # SSH Port group
                ssh_group = group_id

    if group_id:
        logger.debug("{instance}: Opening port 22 for group {group}".format(instance=ec2_instance_id,
                                                                            group=group_id))
        ec2.authorize_ssh(ssh_group or group_id)
        logger.debug("{instance}: SSH port 22 opened".format(instance=ec2_instance_id))

    return ssh_group or group_id


# Revokes SSH authorization on port 22 for the given instance
def revoke_ssh_authorization(ec2_instance_id, group, logger):
    if group:
        logger.debug("{instance}: Closing port 22 for {group}".format(instance=ec2_instance_id, group=group))
        ec2.revoke_ssh(group)
        logger.debug("{instance}: SSH port 22 closed for {group}".format(instance=ec2_instance_id, group=group))


# Formats AWS file
def format_aws_file(file_base_name, ec2_instance):
    ydm = datetime.now().strftime("%Y%d%m")
    return "{instance}_{datetime}_{file}".format(instance=ec2_instance,
                                                 datetime=ydm, file=file_base_name)
