#!/usr/bin/bash
#
# Some basic monitoring functionality; Tested on Amazon Linux 2 
#
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
INSTANCE_TYPE=$(curl -s http://169.254.169.254/latest/meta-data/instance-type)
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
IMAGE_ID=$(curl -s http://169.254.169.254/latest/meta-data/ami-id)
MEMORYUSAGE=$(free -m | awk 'NR==2{printf "%.2f%%", $3*100/$2 }')
PROCESSES=$(expr $(ps -A | grep -c .) - 1)
HTTPD_PROCESSES=$(ps -A | grep -c httpd)

echo "Instance ID: $INSTANCE_ID"
echo "Memory utilisation: $MEMORYUSAGE"
echo "No of processes: $PROCESSES"
echo "Public IP address : $PUBLIC_IP"
echo "Instance type: $INSTANCE_TYPE"
echo "ImageId : $IMAGE_ID"
echo "The user is : "$(whoami)
echo "Disk space usage :"
df -h
if [ $HTTPD_PROCESSES -ge 1 ]
then
    echo "Web server is running"
else
    echo "Web server is NOT running"
fi





