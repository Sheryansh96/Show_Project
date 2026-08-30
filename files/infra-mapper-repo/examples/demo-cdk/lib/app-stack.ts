import * as cdk from 'aws-cdk-lib';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecs_patterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as apigatewayv2 from 'aws-cdk-lib/aws-apigatewayv2';
import { Construct } from 'constructs';

export class AppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const cluster = new ecs.Cluster(this, 'AppCluster', { vpc });

    const queue = new sqs.Queue(this, 'OrdersQueue');

    const ordersTable = new dynamodb.Table(this, 'OrdersTable', {
      partitionKey: { name: 'orderId', type: dynamodb.AttributeType.STRING },
    });

    const assetsBucket = new s3.Bucket(this, 'AssetsBucket');

    // Public-facing API behind an ALB
    const apiService = new ecs_patterns.ApplicationLoadBalancedFargateService(this, 'ApiService', {
      cluster,
      desiredCount: 2,
      taskImageOptions: {
        image: ecs.ContainerImage.fromAsset('../services/api-service'),
        containerPort: 8080,
        environment: {
          QUEUE_URL: queue.queueUrl,
          LOG_LEVEL: 'info',
        },
      },
    });

    // Background worker task: app container + log router sidecar
    const workerTaskDef = new ecs.FargateTaskDefinition(this, 'WorkerTaskDef', {
      cpu: 512,
      memoryLimitMiB: 1024,
    });

    const workerContainer = workerTaskDef.addContainer('WorkerContainer', {
      image: ecs.ContainerImage.fromAsset('../services/worker-service'),
      environment: {
        QUEUE_URL: queue.queueUrl,
        TABLE_NAME: ordersTable.tableName,
        BATCH_SIZE: '10',
      },
      command: ['node', 'dist/worker.js'],
      portMappings: [],
    });

    const logRouter = workerTaskDef.addContainer('LogRouter', {
      image: ecs.ContainerImage.fromRegistry('amazon/aws-for-fluent-bit:latest'),
      portMappings: [{ containerPort: 24224 }],
    });

    const workerService = new ecs.FargateService(this, 'WorkerService', {
      cluster,
      taskDefinition: workerTaskDef,
      desiredCount: 3,
    });

    ordersTable.grantReadWriteData(workerTaskDef.taskRole);
    queue.grantConsumeMessages(workerTaskDef.taskRole);

    // Notify lambda: fires SES emails, triggered off a REST API
    const notifyLambda = new lambda.Function(this, 'NotifyLambda', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('../services/notify-lambda'),
      environment: {
        TABLE_NAME: ordersTable.tableName,
      },
    });

    ordersTable.grantReadData(notifyLambda);
    assetsBucket.grantRead(notifyLambda);

    const notifyApi = new apigateway.RestApi(this, 'NotifyApi');
    notifyApi.root.addResource('notify').addMethod('POST', new apigateway.LambdaIntegration(notifyLambda));

    const httpApi = new apigatewayv2.HttpApi(this, 'PublicHttpApi');
    httpApi.addRoutes({
      path: '/{proxy+}',
      integration: new HttpAlbIntegration('ApiIntegration', apiService.listener),
    });
  }
}
