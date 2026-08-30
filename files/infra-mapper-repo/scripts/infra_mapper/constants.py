"""Static tables and compiled regexes for the CDK construct scanner.

This is not a TS AST — it recognizes specific CDK L2 idioms via regex plus
brace-balancing. See the package docstring / README for the supported shapes.
"""
import re

IGNORE_DIRS = {".git", "node_modules", "cdk.out", "dist", "build", ".venv"}

RESOURCE_TYPES = {
    "dynamodb.Table": "table",
    "sqs.Queue": "queue",
    "sns.Topic": "topic",
    "s3.Bucket": "bucket",
    "lambda.Function": "lambda",
    "apigateway.RestApi": "api",
    "apigateway.LambdaRestApi": "api",
    "apigatewayv2.HttpApi": "api",
}
KNOWN_NAMESPACES = {"ecs", "ecs_patterns", "dynamodb", "sqs", "sns", "s3", "lambda", "apigateway", "apigatewayv2"}

# CDK v2 code just as commonly uses named imports (`import { Table } from
# 'aws-cdk-lib/aws-dynamodb'; new Table(this, 'Id', {...})`) as the
# `import * as ns` + `new ns.Table(...)` idiom. CONSTRUCT_RE below matches a
# bare class name too; this table is how a bare name resolves to the same
# canonical `ns.Class` type string the namespaced path already produces.
# NodejsFunction/GoFunction/PythonFunction/DockerImageFunction all behave
# like lambda.Function for this tool's purposes (they still take `this`,
# an id, `environment`, and some code-source field).
CLASS_TO_CTYPE = {
    "Cluster": "ecs.Cluster",
    "FargateTaskDefinition": "ecs.FargateTaskDefinition",
    "Ec2TaskDefinition": "ecs.Ec2TaskDefinition",
    "FargateService": "ecs.FargateService",
    "Ec2Service": "ecs.Ec2Service",
    "ApplicationLoadBalancedFargateService": "ecs_patterns.ApplicationLoadBalancedFargateService",
    "NetworkLoadBalancedFargateService": "ecs_patterns.NetworkLoadBalancedFargateService",
    "Table": "dynamodb.Table",
    "Queue": "sqs.Queue",
    "Topic": "sns.Topic",
    "Bucket": "s3.Bucket",
    "Function": "lambda.Function",
    "NodejsFunction": "lambda.Function",
    "GoFunction": "lambda.Function",
    "PythonFunction": "lambda.Function",
    "DockerImageFunction": "lambda.Function",
    "RestApi": "apigateway.RestApi",
    "LambdaRestApi": "apigateway.LambdaRestApi",
    "HttpApi": "apigatewayv2.HttpApi",
}

IMPORT_ALIAS_RE = re.compile(
    r"import\s+\*\s+as\s+(\w+)\s+from\s+['\"](?:@aws-cdk/aws-|aws-cdk-lib/aws-)([\w-]+)['\"]"
)

CONSTRUCT_RE = re.compile(
    r"(?:const\s+(\w+)\s*=\s*)?new\s+(?:(\w+)\.)?([A-Za-z]\w*)\(\s*this\s*,\s*['\"]([^'\"]+)['\"]\s*,?"
)
ENTRY_JOIN_RE = re.compile(r"entry\s*:\s*join\(\s*__dirname\s*,\s*([^)]*)\)")
ENTRY_LITERAL_RE = re.compile(r"entry\s*:\s*['\"]([^'\"]+)['\"]")
INTEGRATION_ASSIGN_RE = re.compile(r"const\s+(\w+)\s*=\s*new\s+(?:\w+\.)?LambdaIntegration\(\s*(\w+)")
ADD_RESOURCE_ASSIGN_RE = re.compile(r"const\s+(\w+)\s*=\s*(\w+)\.(?:root\.)?addResource\(")
ADD_METHOD_RE = re.compile(r"(\w+)\.addMethod\(\s*['\"][^'\"]+['\"]\s*,\s*(\w+)")
ADD_CONTAINER_RE = re.compile(r"(?:const\s+(\w+)\s*=\s*)?(\w+)\.addContainer\(\s*['\"]([^'\"]+)['\"]\s*,?")
IMAGE_ASSET_RE = re.compile(r"ContainerImage\.fromAsset\(\s*['\"]([^'\"]+)['\"]")
IMAGE_REGISTRY_RE = re.compile(r"ContainerImage\.fromRegistry\(\s*['\"]([^'\"]+)['\"]")
IMAGE_ECR_RE = re.compile(r"ContainerImage\.fromEcrRepository\(\s*(\w+)")
CODE_ASSET_RE = re.compile(r"Code\.fromAsset\(\s*['\"]([^'\"]+)['\"]")
PORT_RE = re.compile(r"containerPort\s*:\s*(\d+)")
COMMAND_RE = re.compile(r"command\s*:\s*\[([^\]]*)\]")
CPU_RE = re.compile(r"\bcpu\s*:\s*(\d+)")
MEM_RE = re.compile(r"memoryLimitMiB\s*:\s*(\d+)")
DESIRED_RE = re.compile(r"desiredCount\s*:\s*(\d+)")
CLUSTER_REF_RE = re.compile(r"cluster\s*:\s*(\w+)|(?<!\.)\bcluster\b\s*,")
TASKDEF_REF_RE = re.compile(r"taskDefinition\s*:\s*(\w+)|(?<!\.)\btaskDefinition\b\s*,")
TASK_IMAGE_OPTS_RE = re.compile(r"taskImageOptions\s*:\s*\{")
RUNTIME_RE = re.compile(r"runtime\s*:\s*lambda\.Runtime\.(\w+)")
HANDLER_RE = re.compile(r"handler\s*:\s*['\"]([^'\"]+)['\"]")
PARTITION_KEY_RE = re.compile(r"name\s*:\s*['\"]([^'\"]+)['\"]")
GRANT_RE = re.compile(r"(\w+)\.grant(\w*)\(\s*(\w+)")
LAMBDA_INTEGRATION_ROUTE_RE = re.compile(
    r"(\w+)\.root\.addResource\([^()]*\)\.addMethod\(\s*['\"][^'\"]+['\"]\s*,\s*new (?:\w+\.)?LambdaIntegration\(\s*(\w+)"
)
LAMBDA_INTEGRATION_BARE_RE = re.compile(r"new (?:\w+\.)?LambdaIntegration\(\s*(\w+)")
ADD_ROUTES_RE = re.compile(r"(\w+)\.addRoutes\(")
ALB_INTEGRATION_RE = re.compile(r"HttpAlbIntegration\([^,)]*,\s*(\w+)")

ENV_VAR_REF_RE = re.compile(r"(\w+)\.")
