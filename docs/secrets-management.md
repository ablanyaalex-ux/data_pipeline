# Secret Management for our Extractors

## Challenge

Many of our upcoming extractors will need to access sensitive information such as API keys, database passwords, and other credentials.
We need to access these secrets securely, ideally they don't live in our machine or in our codebase.
We need to maintain our nice testing infrastructure so we can be sure that if the environment relfects our assumptions, our extractors will work as expected.
An example with urgency is the Verint extractor where we need API keys to access the data.

## Background

Azure has a KeyVault service that we already use in other projects and works well for our needs: https://azure.microsoft.com/en-us/products/key-vault/
We could potentially use environment variables or another fabric/code-level solution but it would not be as secure or manageable as a dedicated secret management service.
I didn't find any other good alternatives.

## Solution

I created an abstract class called SecretProvider that defines a simple interface for getting secrets by name (purely key-value): https://dev.azure.com/TAG-DataEngineering-Fabric/_git/Exploration?path=/krishan/src/tag_data_engineering/secrets/secret_provider.py

The Azure subclass implements pulling secrets from Azure KeyVault: https://dev.azure.com/TAG-DataEngineering-Fabric/_git/Exploration?path=/krishan/src/tag_data_engineering/secrets/azure_secret_provider.py

A SecretProvider object is now required by the BaseExtractor and all extractors that need secrets can use it to get their secrets securely: https://dev.azure.com/TAG-DataEngineering-Fabric/_git/Exploration?path=/krishan/src/tag_data_engineering/extractors/base_extractor.py

I added a dummy secret for the star wars API to show how it will work: https://dev.azure.com/TAG-DataEngineering-Fabric/_git/Exploration?path=/krishan/src/tag_data_engineering/extractors/rest_api_extractor.py&version=GBsecrets&line=45&lineEnd=48&lineStartColumn=1&lineEndColumn=1&lineStyle=plain&_a=contents

I created a MockSecretProvider for testing purposes so we can keep our existing test infrastructure: https://dev.azure.com/TAG-DataEngineering-Fabric/_git/Exploration?path=/krishan/src/tag_data_engineering/secrets/mock_secret_provider.py

The mock secret provider is used like this:
https://dev.azure.com/TAG-DataEngineering-Fabric/_git/Exploration?path=/krishan/tests_integration/conftest.py&version=GBsecrets&line=183&lineEnd=207&lineStartColumn=1&lineEndColumn=1&lineStyle=plain&_a=contents
https://dev.azure.com/TAG-DataEngineering-Fabric/_git/Exploration?path=/krishan/tests_integration/pipeline_executor.py&version=GBsecrets&line=123&lineEnd=145&lineStartColumn=1&lineEndColumn=1&lineStyle=plain&_a=contents
So now all the local tests pass.

To deploy the pipeline, we now need to pass the KeyVault URL into the constructor of the AzureKeyVaultSecretProvider. This is done by having a template variable in the pipeline execution notebook:
https://dev.azure.com/TAG-DataEngineering-Fabric/_git/Exploration?path=/krishan/jobs/notebook/run_transformation.ipynb&version=GBsecrets&line=46&lineEnd=47&lineStartColumn=1&lineEndColumn=1&lineStyle=plain&_a=contents

We replace this placeholder during deployment here:
https://dev.azure.com/TAG-DataEngineering-Fabric/_git/Exploration?path=/krishan/src/tag_data_engineering/deployment/fabric_deployment.py&version=GBsecrets&line=111&lineEnd=112&lineStartColumn=1&lineEndColumn=1&lineStyle=plain&_a=contents

## New Challenges

1. The deployed pipeline now depends on the KeyVault being accessible by the executor of the pipeline. Currently this is failing as you can see here:
https://app.powerbi.com/workloads/data-pipeline/artifactAuthor/workspaces/a63e9e63-86be-4221-9ffe-4b0b11ec9997/pipelines/3b8da48c-fcd2-45d2-bbc8-c8fc1121b28f/b1cdf64b-76a1-4c9a-b7ad-631ec2d7621d?trident=1&experience=fabric-developer&ctid=b3b5c005-2c13-4fcc-8eb8-8cc6b0854bee
The running instance cannot access its Azure crendetials, and even if it could, it would use my user. We need to find a deployment and execution strategy that uses a managed identity or service principal or something else with access to the KeyVault.
2. We need to manage the secrets in the KeyVault. Who has access to add/remove secrets? How do we rotate them? This is more of an operational challenge than a technical one but we need to address it.
