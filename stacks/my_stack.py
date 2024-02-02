from email.policy import default
from constructs import Construct
from aws_cdk import (
    Duration,
    CfnOutput,
    Stack,
    CustomResource,
    aws_lambda as lambda_,
    aws_dynamodb as ddb,
    aws_iot as iot,
    aws_iam as iam
)
import aws_cdk as cdk
import logging


class FeedmyfurbabiesPipelineCdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)

        # Parameters
        cat_feeder_thing_lambda_name = cdk.CfnParameter(self, "CatFeederThingLambdaName", type="String", default="CatFeederThingLambda")
        cat_feeder_thing_lambda_action_topic_name = cdk.CfnParameter(self, "CatFeederThingLambdaActionTopicName", type="String", default="cat-feeder/action")
        cat_feeder_thing_controller_name = cdk.CfnParameter(self, "CatFeederThingControllerName", type="String", default="CatFeederThingESP32")
        cat_feeder_thing_controller_states_topic_name = cdk.CfnParameter(self, "CatFeederThingControllerStatesTopicName", type="String", default="cat-feeder/states")








        # IAM Role for Lambda Function
        custom_resource_lambda_role = iam.Role(
            self, "CustomResourceExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # IAM Policies
        iot_policy = iam.PolicyStatement(
            actions=[
                "iot:CreateCertificateFromCsr",
                "iot:CreateKeysAndCertificate",
                "iot:DescribeEndpoint",
                "iot:AttachPolicy",
                "iot:DetachPolicy",
                "iot:UpdateCertificate",
                "iot:DeleteCertificate"
            ],
            resources=["*"]  # Modify this to restrict to specific secrets
        )

        # IAM Policies
        ssm_policy = iam.PolicyStatement(
            actions=[
                "ssm:PutParameter",
                "ssm:DeleteParameters"
            ],
            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/*"]  # Modify this to restrict to specific secrets
        )

        logging_policy = iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=["arn:aws:logs:*:*:*"]
        )
       
        custom_resource_lambda_role.add_to_policy(iot_policy)
        custom_resource_lambda_role.add_to_policy(ssm_policy)
        custom_resource_lambda_role.add_to_policy(logging_policy)

        # Define the Lambda function
        custom_lambda = lambda_.Function(
            self, 'CustomResourceLambdaIoT',
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler="app.handler",
            code=lambda_.Code.from_asset("lambdas/custom-resources/iot"),
            timeout=Duration.seconds(60),
            role=custom_resource_lambda_role
        )


        # Properties to pass to the custom resource
        custom_resource_props = {
            "EncryptionAlgorithm": "ECC",
            "CatFeederThingLambdaCertName": f"{cat_feeder_thing_lambda_name.value_as_string}",
            "CatFeederThingControllerCertName": f"{cat_feeder_thing_controller_name.value_as_string}",
            "StackName": f"{construct_id}",
        }

        # Create the Custom Resource
        custom_resource = CustomResource(
            self, 'CustomResourceIoT',
            service_token=custom_lambda.function_arn,
            properties=custom_resource_props
        )









        thing_lambda = iot.CfnThing(self, "CatFeederThingLambda", thing_name=cat_feeder_thing_lambda_name.value_as_string,)
        

        # IAM Role for Lambda Function
        lambda_role = iam.Role(
            self, "PublishToESP32ThingExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # IAM Policies
        secrets_policy = iam.PolicyStatement(
            actions=[
                "ssm:GetParameter"
            ],
            resources=["*"]  
        )
        

        lambda_role.add_to_policy(secrets_policy)
        lambda_role.add_to_policy(logging_policy)

        # Lambda Function
        lambda_function = lambda_.Function(
            self, "CatFeederThingFunction",
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler="app.lambda_handler",
            code=lambda_.Code.from_asset("lambdas/cat-feeder/thing"),
            environment={
                "Topic": cat_feeder_thing_lambda_action_topic_name.value_as_string,
                "ThingName": cat_feeder_thing_lambda_name.value_as_string,
                "PrivateKeySecretParameter": custom_resource.get_att_string("PrivateKeySecretParameterLambda"),
                "CertificatePemParameter": custom_resource.get_att_string("CertificatePemParameterLambda"),
                "AmazonRootCAParameter": custom_resource.get_att_string("AmazonRootCAParameterLambda"),
                "IoTEndpoint": custom_resource.get_att_string("DataAtsEndpointAddress")
            }, 
            role=lambda_role
        )


        
        # IoT Policy (Lambda)
        cat_feeder_thing_lambda_policy = iot.CfnPolicy(
            self, "CatFeederThingLambdaPolicy",
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "iot:Connect",
                        "Resource": f"arn:aws:iot:{self.region}:{self.account}:client/{cat_feeder_thing_lambda_name.value_as_string}"
                    },
                    {
                        "Effect": "Allow",
                        "Action": "iot:Publish",
                        "Resource": f"arn:aws:iot:{self.region}:{self.account}:topic/{cat_feeder_thing_lambda_action_topic_name.value_as_string}"
                    }
                ]
            },
            policy_name=cat_feeder_thing_lambda_name.value_as_string
        )

        iot.CfnPolicyPrincipalAttachment(
            self, "CatFeederThingLambdaPolicyPrincipalAttachment",
            policy_name=cat_feeder_thing_lambda_name.value_as_string,
            principal=custom_resource.get_att_string("CertificateArnLambda"),
        )

        thing_principal_attachment_lambda = iot.CfnThingPrincipalAttachment(
            self, "CatFeederThingLambdaPrincipalAttachment",
            thing_name=cat_feeder_thing_lambda_name.value_as_string,
            principal=custom_resource.get_att_string("CertificateArnLambda"),
        )

        thing_principal_attachment_lambda.add_depends_on(thing_lambda)










        cat_feeder_thing_controller = iot.CfnThing(
            self, "CatFeederThingController",
            thing_name=cat_feeder_thing_controller_name.value_as_string,
            attribute_payload=iot.CfnThing.AttributePayloadProperty(
                attributes={"thingType": "esp32"}
            )
        )

            
        # IoT Policy (Controller)
        cat_feeder_thing_controller_policy = iot.CfnPolicy(
            self, "CatFeederThingControllerPolicy",
            policy_document = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "iot:Connect",
                        "Resource": f"arn:aws:iot:{self.region}:{self.account}:client/{cat_feeder_thing_controller_name.value_as_string}"
                    },
                    {
                        "Effect": "Allow",
                        "Action": "iot:Subscribe",
                        "Resource": f"arn:aws:iot:{self.region}:{self.account}:topicfilter/{cat_feeder_thing_lambda_action_topic_name.value_as_string}"
                    },
                    {
                        "Effect": "Allow",
                        "Action": "iot:Receive",
                        "Resource": f"arn:aws:iot:{self.region}:{self.account}:topic/{cat_feeder_thing_lambda_action_topic_name.value_as_string}"
                    },
                    {
                        "Effect": "Allow",
                        "Action": "iot:Publish",
                        "Resource": f"arn:aws:iot:{self.region}:{self.account}:topic/{cat_feeder_thing_controller_states_topic_name.value_as_string}"
                    }
                ]
            },
            policy_name=cat_feeder_thing_controller_name.value_as_string
        )

        iot.CfnPolicyPrincipalAttachment(
            self, "CatFeederThingControllerPolicyPrincipalAttachment",
            policy_name=cat_feeder_thing_controller_name.value_as_string,
            principal=custom_resource.get_att_string("CertificateArnController"),
        )

        thing_principal_attachment_controller = iot.CfnThingPrincipalAttachment(
            self, "CatFeederThingControllerPrincipalAttachment",
            thing_name=cat_feeder_thing_controller_name.value_as_string,
            principal=custom_resource.get_att_string("CertificateArnController"),
        )

        thing_principal_attachment_controller.add_depends_on(cat_feeder_thing_controller)









        CfnOutput(
            self, "DataAtsEndpointAddress",
            value=custom_resource.get_att_string("DataAtsEndpointAddress"),
            description="This is the Data ATS Endpoint"
        )



