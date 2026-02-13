from botocore.stub import Stubber
import boto3

from tactus.registry.sagemaker import SageMakerRegistry


def test_sagemaker_registry_list_versions():
    client = boto3.client("sagemaker", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_response(
        "list_model_packages",
        {
            "ModelPackageSummaryList": [
                {
                    "ModelPackageName": "demo-1",
                    "ModelPackageVersion": 1,
                    "CreationTime": 1.0,
                    "ModelPackageArn": "arn:aws:sagemaker:demo",
                    "ModelPackageStatus": "Completed",
                }
            ]
        },
        {"NameContains": "demo"},
    )
    stubber.activate()

    registry = SageMakerRegistry(client=client)
    versions = registry.list_versions("demo")
    stubber.deactivate()

    assert versions[0].version_id == 1
