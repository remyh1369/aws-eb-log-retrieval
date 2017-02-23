# aws-eb-log-retrieval - Guide

1. Configure the EB environments you want to monitor with the required parameters:
    - Log files to retrieve
    - Does the rotation of some log files need to be taken care of?
    - Key pem file path for each of your EB environment
    - Use private or public EC2 instance IPs whether or not you're within a VPN
    - The backup file name and directory so that the service can get the latest information of the logs retrieved
    - How often do you want to check the EC2 instances and retrieve their logs (in seconds)
    - Your AWS credentials, that's optional if they're set up in your local environment
    - You can also indicate if you want to keep on disk the log files retrieved from EC2 machines
    - If you need to send your logs to a third party platform, please provide an API endpoint for each EB environment


2. Unit tests:
    - One or multiple of your EC2 instances to retrieve logs
    `python3 -m unit_tests.ut_tail_ec2_instance`
    
    - One or multiple of your EB environments to automatically retrieve logs from all their instances
    `python3 -m unit_tests.ut_tail_eb_environment`
    
    - EB log retrieval service to make sure you can start the log retrieval job as a constantly running process
    `python3 -m unit_tests.ut_eb_log_retrieval_service`

3. Test the EB log retrieval service before setting up Upstart:
    `python3 -m runner config/aws_eb_log_retrieval_sample.yml`

4. Setup a constantly running process. To do that, you can add a job configuration file in /etc/init on your server
    **Upstart example for /etc/init/aws_eb_log_retrieval.conf**
    ```
    description "Job for constantly tailing new Elastic Beanstalk log files" \
        "and sending them to Sumologic endpoints"
    author "rhuberdeau"
    
    start on runlevel [2345]
    
    script
            cd /path/to/your/aws_eb_log_retrieval/repository
            exec python3 -m runner config/aws_eb_log_retrieval_sample.yml
    end script
    ```

5. Start you service `sudo service /etc/init/aws_eb_log_retrieval start`

6. Check your backup file to make sure logs from EC2 instances are being retrieved

7. Monitor logs in your third-party platform

8. If you want to update your EB log retrieval configuration, you can simply send a user signal to the running service. 
Get the process PID and execute the following: 
`kill -s SIGURS1 [PID]`
Your updated yml config file will be immediately reloaded if the process is currently sleeping or will be reloaded if the process is currently processing logs