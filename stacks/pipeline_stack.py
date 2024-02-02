from constructs import Construct
from aws_cdk import (
    Stack,
    aws_codecommit as codecommit,
    pipelines as pipelines,
)
from stacks.pipeline_stage import PipelineStage

class PipelineStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        resource_prefix = id + '-'

        # Creates a CodeCommit repository called 'WorkshopRepo'
        repo = codecommit.Repository(
            self, 'FeedMyFurBabiesCodeCommitRepo',
            repository_name= resource_prefix + "FeedMyFurBabiesCodeCommitRepo"
        )

        pipeline = pipelines.CodePipeline(
            self,
            "Pipeline",
            docker_enabled_for_synth=True,
            docker_enabled_for_self_mutation=True,
            synth=pipelines.ShellStep(
                "Synth",
                input=pipelines.CodePipelineSource.code_commit(repo, "main"),
                commands=[
                    "npm install -g aws-cdk",  # Installs the cdk cli on Codebuild
                    "pip install -r requirements.txt",  # Instructs Codebuild to install required packages
                    "cdk synth",
                ]
            ),
        )

        deploy = PipelineStage(self, "Deploy", resource_prefix)
        deploy_stage = pipeline.add_stage(deploy)
