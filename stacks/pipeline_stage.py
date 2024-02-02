from constructs import Construct
from aws_cdk import (
    Stage
)
from stacks.my_stack import FeedmyfurbabiesPipelineCdkStack

class PipelineStage(Stage):

    def __init__(self, scope: Construct, id: str, resource_prefix: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        service = FeedmyfurbabiesPipelineCdkStack(self, resource_prefix + 'deployed-service')