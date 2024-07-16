import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

export class BedrockSdkLayer extends Construct {
    public readonly layer: lambda.LayerVersion;

    constructor(scope: Construct, id: string) {
        super(scope, id);

        this.layer = new lambda.LayerVersion(this, 'BedrockSdkLayer', {
            code: lambda.Code.fromAsset('../../lambda/layers/bedrock-sdk-layer'),
            compatibleRuntimes: [lambda.Runtime.PYTHON_3_9],
            description: 'Lambda layer containing the AWS SDK with Bedrock support',
        });

        new cdk.CfnOutput(this, 'BedrockSdkLayerArn', {
            value: this.layer.layerVersionArn,
            description: 'ARN of the Bedrock SDK Lambda Layer',
            exportName: 'BedrockSdkLayerArn',
        });
    }
}