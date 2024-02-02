import os
import boto3
import json 
from botocore.exceptions import ClientError

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

def lambda_handler(event, context):
    certificate_pem_parameter_name = os.environ['CertificatePemParameter']
    private_key_secret_parameter_name = os.environ['PrivateKeySecretParameter']
    amazon_root_ca_parameter_name = os.environ['AmazonRootCAParameter']


    ssm = boto3.client('ssm')

    try:
        certificate_pem_response = ssm.get_parameter(Name=certificate_pem_parameter_name, WithDecryption=True)
        private_key_secret_private_response = ssm.get_parameter(Name=private_key_secret_parameter_name, WithDecryption=True)
        amazon_root_ca_response = ssm.get_parameter(Name=amazon_root_ca_parameter_name, WithDecryption=True)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print("The requested secret was not found")
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            print("The request was invalid due to:", e)
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            print("The request had invalid params:", e)
        else:
            print(e)

        return False
    else:
        text_secret_data_cert_ca = amazon_root_ca_response['Parameter']['Value']
        text_secret_data_cert_crt = certificate_pem_response['Parameter']['Value']
        text_secret_data_cert_private = private_key_secret_private_response['Parameter']['Value']


        with open('/tmp/root_ca.pem', 'w') as the_file:
            the_file.write(text_secret_data_cert_ca)

        with open('/tmp/device_cert.crt', 'w') as the_file:
            the_file.write(text_secret_data_cert_crt)

        with open('/tmp/private_key.key', 'w') as the_file:
            the_file.write(text_secret_data_cert_private)

        myMQTTClient = AWSIoTMQTTClient(os.environ['ThingName'])
        myMQTTClient.configureEndpoint(os.environ['IoTEndpoint'], 8883)
        myMQTTClient.configureCredentials("/tmp/root_ca.pem", "/tmp/private_key.key", "/tmp/device_cert.crt")
        myMQTTClient.configureOfflinePublishQueueing(-1) 
        myMQTTClient.configureDrainingFrequency(2)  
        myMQTTClient.configureConnectDisconnectTimeout(10) 
        myMQTTClient.configureMQTTOperationTimeout(5)  

        myMQTTClient.connect()
   
        dictionary ={ 
            "event": "Feedme",
            "reportedTime": "1234567890"
        }

        myMQTTClient.publish(os.environ['Topic'], json.dumps(dictionary), 0)
        myMQTTClient.disconnect()

    return "Sent MQTT message to " + os.environ['Topic']
