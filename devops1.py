import webbrowser
import botocore
import boto3
import sys
import time
from datetime import datetime,timedelta
import requests
import subprocess
from configparser import ConfigParser


#Try and except in create instance and subprocess


#------------------General variables------------------

#Variables from a config file with configparser

config = ConfigParser()
#Read from configfile.ini 
config.read("configfile.ini")

#It kinda work like a list of dictionaries
ec2_config = config["ec2_config"]
bucket_config = config["bucket_config"]
logo_config = config["logo_config"]

#ec2_config
MyKeyName = ec2_config["key_name"]
MySecurityGroup = ec2_config["security_group"]

#bucket_config
MyACL = bucket_config["ACL"]

#image_url
image_url = logo_config["image_url"] 

#debugging
#print(MyKeyName)
#print(MySecurityGroup)
#print(MyACL)


#Get the ImageId up to date-------------

#this give the latest AMI for the amazon linux instance
getAMI = "aws ssm get-parameters --names /aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2 --query 'Parameters[0].[Value]' --output text"

#We will use subprocess to execute the command and capture the output
latestAMI = subprocess.run([getAMI],shell=True, capture_output=True, text=True).stdout

#debugging
#print(latestAMI)
#the output is a little bit weird : b'ami-0c4e4b4eb2e11d1d4\n' , we need to add text=True to not have a binary sequence of bytes

#we need to add .strip() or else the imageID parameter does not capture properly the value

try:
  ec2 = boto3.resource('ec2')
  new_instances = ec2.create_instances(
    ImageId=latestAMI.strip(),
    MinCount=1,
    MaxCount=1,
    InstanceType='t2.nano',
    UserData="""#!/bin/bash
    yum update -y
    yum install httpd -y
    systemctl enable httpd
    systemctl start httpd
    echo "<h1>Quentin Lim DevOps</h1> <ul> <li>Instance ID : $(curl http://169.254.169.254/latest/meta-data/instance-id)</li> <li>AMI ID : $(curl http://169.254.169.254/latest/meta-data/ami-id)</li> <li>Instance type : $(curl http://169.254.169.254/latest/meta-data/instance-type)</li> </ul>" > /var/www/html/index.html;
    """,
    SecurityGroupIds=[MySecurityGroup],
    KeyName=MyKeyName,
    TagSpecifications=[
        {
          'ResourceType': 'instance',
          'Tags' : [
            {
            'Key': 'Name',
            'Value' : 'ec2InstanceDevOpsCA1'
            },
          ]
          
        },
      ]
          
    )
    
except Exception as error:
  print("Instance creation failed")
except botocore.exceptions.ClientError as error:
  print("ClientError :",error)
  
except botocore.exceptions.ParamValidationError as error:
    raise ValueError('The parameters you provided are incorrect: {}'.format(error))  

#Launch server-------------
#reload
new_instances[0].reload()
new_instances[0].wait_until_running()
print("Instance Running")


#------------------instances variables------------------
inst = ec2.Instance(new_instances[0].id)
publicIp = inst.public_ip_address


#Wait for the server to set up----------------
#use of requests
#Instead of using sleep() we will make a while loop until the server is done setting up(verify every 10 seconds)

serverUp=False
while serverUp!=True:
  try:
    r = requests.head('http://'+publicIp)#if it raise a error that means the server is not ready yet
  except:
    print("The server is not done setting up, trying again in 10 seconds")
    time.sleep(10)
  else:
    serverUp =True
    print("The server is done setting up !")
  
#print(r)
#200 code means it's ok

print ("Instance ID :",inst.id)



#Bucket--------------------------------------------------------

#Create Bucket
s3 = boto3.resource("s3")
#make unique bucket_name
bucket_name = "ql2111-"+str(datetime.now().strftime("%d-%m-%Y-%H-%M-%S"))
#Make it public by default with ACL='public-read'
try:
  response = s3.create_bucket(
    ACL=MyACL,
    Bucket=bucket_name)
  #print(response)
except botocore.exceptions.ClientError as error:
  print("ClientError :",e)
  
print("Bucket name : "+bucket_name)


#Put Bucket-------------

#object_name to fetch at http://devops.witdemo.net/logo.jpg


#Get the image with requests

try:
  response = requests.get(image_url)
  #status code of 200 mean that it's OK
  if response.status_code == 200:
    with open("image.png", 'wb') as f:
      f.write(response.content)
except requests.exceptions.HTTPError as errorH:
  print ("Http Error:",errorH)
except requests.exceptions.ConnectionError as errC:
  print ("Error Connecting:",errC)
except requests.exceptions.Timeout as errT:
  print ("Timeout Error:",errT)
except requests.exceptions.RequestException as err:
  print (err)


#Upload the image-------------

object_name = "image.png"
#put the image in the bucket
try:
    response = s3.Object(bucket_name, object_name).put(
      ACL=MyACL,
      Body=open(object_name, 'rb'),
      ContentType='image/jpeg')
    #print (response)
except Exception as error:
    print (error)
    
       
#Creating the index.html file and overwrite its content

#Construct the link
link = '<img src="https://'+str(bucket_name)+'.s3.amazonaws.com/image.png">'
#print(link)      #debugging
print("The image is from :",image_url)

#try:
f = open("index.html", "w")
f.write("<h1>Quentin Lim -DevOps </h1>\n")
f.write(link)
f.close()

#Upload the index.html

object_name = "index.html"
try:
    response = s3.Object(bucket_name, object_name).put(
      ACL=MyACL,
      Body=open(object_name, 'rb'),
      ContentType='text/html')
    #print (response)
except Exception as error:
    print (error)


    
#Static website configuration-------------
website_configuration = {
 'ErrorDocument': {'Key': 'error.html'},
 'IndexDocument': {'Suffix': 'index.html'},
}
bucket_website = s3.BucketWebsite(bucket_name)
response = bucket_website.put(WebsiteConfiguration=website_configuration)



#Launch a web browser (EC2 and S3)-------------
webbrowser.open_new_tab('http://'+publicIp)
webbrowser.open_new_tab('http://'+bucket_name+'.s3-website-us-east-1.amazonaws.com')


#write the 2 URLs to a file called quentin.txt
f = open("quentin.txt", "w")
f.write('EC2 link : http://'+publicIp+"\n")
f.write('S3 link : http://'+bucket_name+'.s3-website-us-east-1.amazonaws.com')
f.close()


#Monitoring
print("------------Monitoring-------------\n")
#use scp to copy monitor.sh use subprocess

inst.reload()


cmd1 = 'scp -o StrictHostKeyChecking=no -i '+MyKeyName+'.pem monitor.sh ec2-user@'+publicIp+':.'
cmd2 = 'ssh -i '+MyKeyName+'.pem ec2-user@'+publicIp+' chmod 700 monitor.sh'
cmd3 ='ssh -i '+MyKeyName+'.pem ec2-user@'+publicIp+' ./monitor.sh'


#debugging
#print(cmd1)
#print(cmd2)
#print(cmd3)

#cmd1 is a string and not a sequence fo arguments so we put shell=True


process1 = subprocess.run([cmd1], shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
process2 = subprocess.run([cmd2], shell=True)
process3 = subprocess.run([cmd3], shell=True)

#Output and error handling
#TO-DO, doesn't work
#print(process1.stdout)
#print(process1.stderr)

#Cloudwatch---------------------------------------

print("------------CloudWatch-------------")

#Metrics = CPU_Usage, NetworkIn and NetworkOut
cloudwatch = boto3.resource('cloudwatch')

#reloading the instance
inst.reload()
#print(inst.id)

print('\nCloudwatch waiting for data, please wait for a bit')
inst.monitor()  # Enables detailed monitoring on instance (1-minute intervals)
time.sleep(300)     # Wait 5 minutes to ensure we have some data (can remove if not a new instance)
print('Cloudwatch done collecting some data !')



#CPU usage
try:
  metricCPU = cloudwatch.metrics.filter(Namespace='AWS/EC2',
                                              MetricName='CPUUtilization',
                                              Dimensions=[{'Name':'InstanceId', 'Value': inst.id}])
except Exception as error:
    print (error)

#debugging
#metric = list(metricCPU)[0]    # extract first (only) element
#print(metric)


#networkOut
try:
  metricNetworkIn = cloudwatch.metrics.filter(Namespace='AWS/EC2',
                                              MetricName='NetworkIn',
                                              Dimensions=[{'Name':'InstanceId', 'Value': inst.id}])
except Exception as error:
    print (error)                                            
#networkIn
try:
  metricNetworkOut = cloudwatch.metrics.filter(Namespace='AWS/EC2',
                                              MetricName='NetworkOut',
                                              Dimensions=[{'Name':'InstanceId', 'Value': inst.id}])
except Exception as error:
    print (error)

#List of metrics
listMetrics =[]
listMetrics.append(list(metricCPU)[0])
listMetrics.append(list(metricNetworkIn)[0])
listMetrics.append(list(metricNetworkOut)[0])

try:
  for metric in listMetrics:
    response = metric.get_statistics(StartTime = datetime.utcnow() - timedelta(minutes=4),   # 4 minutes ago
                                   EndTime=datetime.utcnow(),                              # now
                                   Period=240,                                             # 4 min intervals
                                   Statistics=['Average'])

    print ("Average "+str(metric.metric_name) +" : "+ str(response['Datapoints'][0]['Average'])+" "+str(response['Datapoints'][0]['Unit']) )
except Exception as error:
    print (error)  
                                  

#print (response)   # for debugging only



