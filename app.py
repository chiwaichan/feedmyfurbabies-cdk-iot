#!/usr/bin/env python3

import aws_cdk as cdk

from stacks.pipeline_stack import PipelineStack


app = cdk.App()
PipelineStack(app, "feedmyfurbabies-cdk-iot")

app.synth()
