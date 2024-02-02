import os
import sys
import json
import logging as logger
import requests
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

import time

logger.getLogger().setLevel(logger.INFO)


def get_aws_client(name):
    return boto3.client(
        name,
        config=Config(retries={"max_attempts": 10, "mode": "standard"}),
    )


def create_resources(thing_name: str, stack_name: str, encryption_algo: str):

    c_iot = get_aws_client("iot")
    c_ssm = get_aws_client("ssm")

    result = {}

    # Download the Amazon Root CA file and save it to Systems Manager Parameter Store
    url = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"
    response = requests.get(url)

    if response.status_code == 200:
        amazon_root_ca = response.text
    else:
        f"Failed to download Amazon Root CA file. Status code: {response.status_code}"


    try:
        # Create the keys and certificate for a thing and save them each as Systems Manager Parameter Store value later
        response = c_iot.create_keys_and_certificate(setAsActive=True)
        certificate_pem = response["certificatePem"]
        private_key = response["keyPair"]["PrivateKey"]
        result["CertificateArn"] = response["certificateArn"]
    except ClientError as e:
        logger.error(f"Error creating certificate, {e}")
        sys.exit(1)  

    # store certificate and private key in SSM param store
    try:
        parameter_private_key = f"/{stack_name}/{thing_name}/private_key"
        parameter_certificate_pem = f"/{stack_name}/{thing_name}/certificate_pem"
        parameter_amazon_root_ca = f"/{stack_name}/{thing_name}/amazon_root_ca"

        # Saving the private key in Systems Manager Parameter Store
        response = c_ssm.put_parameter(
            Name=parameter_private_key,
            Description=f"Certificate private key for IoT thing {thing_name}",
            Value=private_key,
            Type="SecureString",
            Tier="Advanced",
            Overwrite=True
        )
        result["PrivateKeySecretParameter"] = parameter_private_key

        # Saving the certificate pem in Systems Manager Parameter Store
        response = c_ssm.put_parameter(
            Name=parameter_certificate_pem,
            Description=f"Certificate PEM for IoT thing {thing_name}",
            Value=certificate_pem,
            Type="String",
            Tier="Advanced",
            Overwrite=True
        )
        result["CertificatePemParameter"] = parameter_certificate_pem

        # Saving the Amazon Root CA in Systems Manager Parameter Store, 
        # Although this file is publically available to download, it is intended to provide a complete set of files to try out this working example with as much ease as possible
        response = c_ssm.put_parameter(
            Name=parameter_amazon_root_ca,
            Description=f"Amazon Root CA for IoT thing {thing_name}",
            Value=amazon_root_ca,
            Type="String",
            Tier="Advanced",
            Overwrite=True
        )
        result["AmazonRootCAParameter"] = parameter_amazon_root_ca
    except ClientError as e:
        logger.error(f"Error creating secure string parameters, {e}")
        sys.exit(1)

    try:
        response = c_iot.describe_endpoint(endpointType="iot:Data-ATS")
        result["DataAtsEndpointAddress"] = response["endpointAddress"]
    except ClientError as e:
        logger.error(f"Could not obtain iot:Data-ATS endpoint, {e}")
        result["DataAtsEndpointAddress"] = "stack_error: see log files"

    return result

# Delete the resources created for a thing when the CloudFormation Stack is deleted
def delete_resources(thing_name: str, certificate_arn: str, stack_name: str):
    c_iot = get_aws_client("iot")
    c_ssm = get_aws_client("ssm")

    try:
        # Delete all the Systems Manager Parameter Store values created to store a thing's certificate files
        parameter_private_key = f"/{stack_name}/{thing_name}/private_key"
        parameter_certificate_pem = f"/{stack_name}/{thing_name}/certificate_pem"
        parameter_amazon_root_ca = f"/{stack_name}/{thing_name}/amazon_root_ca"
        c_ssm.delete_parameters(Names=[parameter_private_key, parameter_certificate_pem, parameter_amazon_root_ca])
    except ClientError as e:
        logger.error(f"Unable to delete parameter store values, {e}")

    try:
        # Clean up the certificate by firstly revoking it then followed by deleting it
        c_iot.update_certificate(certificateId=certificate_arn.split("/")[-1], newStatus="REVOKED")
        c_iot.delete_certificate(certificateId=certificate_arn.split("/")[-1])
    except ClientError as e:
        logger.error(f"Unable to delete certificate {certificate_arn}, {e}")


def handler(event, context):
    props = event["ResourceProperties"]
    physical_resource_id = ""
    

    try:
        # Check if this is a Create and we're failing Creates
        if event["RequestType"] == "Create" and event["ResourceProperties"].get(
            "FailCreate", False
        ):
            raise RuntimeError("Create failure requested, logging")
        elif event["RequestType"] == "Create":
            logger.info("Request CREATE")

            resp_lambda = create_resources(
                thing_name=props["CatFeederThingLambdaCertName"],
                stack_name=props["StackName"],
                encryption_algo=props["EncryptionAlgorithm"]
            )

            resp_controller = create_resources(
                thing_name=props["CatFeederThingControllerCertName"],
                stack_name=props["StackName"],
                encryption_algo=props["EncryptionAlgorithm"]
            )

            # The values in the response_data could be used in the CDK code, for example used as Outputs for the CloudFormation Stack deployed
            response_data = {
                "CertificateArnLambda": resp_lambda["CertificateArn"],
                "PrivateKeySecretParameterLambda": resp_lambda["PrivateKeySecretParameter"],
                "CertificatePemParameterLambda": resp_lambda["CertificatePemParameter"],
                "AmazonRootCAParameterLambda": resp_lambda["AmazonRootCAParameter"],
                "CertificateArnController": resp_controller["CertificateArn"],
                "PrivateKeySecretParameterController": resp_controller["PrivateKeySecretParameter"],
                "CertificatePemParameterController": resp_controller["CertificatePemParameter"],
                "AmazonRootCAParameterController": resp_controller["AmazonRootCAParameter"],
                "DataAtsEndpointAddress": resp_lambda[
                    "DataAtsEndpointAddress"
                ],
            }

            # Using the ARNs of the pairs of certificates created as the PhysicalResourceId used by Custom Resource
            physical_resource_id = response_data["CertificateArnLambda"] + "," + response_data["CertificateArnController"]
        elif event["RequestType"] == "Update":
            logger.info("Request UPDATE")
            response_data = {}
            physical_resource_id = event["PhysicalResourceId"]
        elif event["RequestType"] == "Delete":
            logger.info("Request DELETE")

            certificate_arns = event["PhysicalResourceId"]
            certificate_arns_array = certificate_arns.split(",")

            resp_lambda = delete_resources(
                thing_name=props["CatFeederThingLambdaCertName"],
                certificate_arn=certificate_arns_array[0],
                stack_name=props["StackName"],
            )

            resp_controller = delete_resources(
                thing_name=props["CatFeederThingControllerCertName"],
                certificate_arn=certificate_arns_array[1],
                stack_name=props["StackName"],
            )
            response_data = {}
            physical_resource_id = certificate_arns
        else:
            logger.info("Should not get here in normal cases - could be REPLACE")

        send_cfn_response(event, context, "SUCCESS", response_data, physical_resource_id)
    except Exception as e:
        logger.exception(e)
        sys.exit(1)


def send_cfn_response(event, context, response_status, response_data, physical_resource_id):
    response_body = json.dumps({
        "Status": response_status,
        "Reason": "See the details in CloudWatch Log Stream: " + context.log_stream_name,
        "PhysicalResourceId": physical_resource_id,
        "StackId": event['StackId'],
        "RequestId": event['RequestId'],
        "LogicalResourceId": event['LogicalResourceId'],
        "Data": response_data
    })

    headers = {
        'content-type': '',
        'content-length': str(len(response_body))
    }

    requests.put(event['ResponseURL'], data=response_body, headers=headers)

