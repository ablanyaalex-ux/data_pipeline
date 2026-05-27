import sys

import click
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


def set_secret(vault_url: str, secret_name: str, secret_value: str) -> None:
    print("Authenticating with Azure...")
    credential = DefaultAzureCredential()
    print(f"Connecting to Key Vault: {vault_url}")
    client = SecretClient(vault_url=vault_url, credential=credential)
    print(f"Setting secret: {secret_name}")
    secret = client.set_secret(secret_name, secret_value)
    print("✅ Secret set successfully!")
    print(f"Secret Name: {secret.name}")
    print(f"Secret Version: {secret.properties.version}")
    print(f"Created On: {secret.properties.created_on}")
    print(f"Updated On: {secret.properties.updated_on}")


@click.command()
@click.option("--vault", "-v", required=True, help="Key Vault name (e.g., 'my-vault' or full URL 'https://my-vault.vault.azure.net/')")
@click.option("--name", "-n", required=True, help="Secret name")
@click.option("--value", help="Secret value (use this OR --file, not both)")
@click.option("--file", "-f", type=click.Path(exists=True), help="Read secret value from file (use this OR --value, not both)")
def main(vault: str, name: str, value: str | None, file: str | None) -> None:
    if value and file:
        print("❌ Error: Cannot specify both --value and --file")
        sys.exit(1)
    if not value and not file:
        print("❌ Error: Must specify either --value or --file")
        sys.exit(1)
    if file:
        print(f"Reading secret from file: {file}")
        with open(file) as f:
            secret_value = f.read().strip()
    else:
        secret_value = value
    if not vault.startswith("https://"):
        vault_url = f"https://{vault}.vault.azure.net/"
    else:
        vault_url = vault
    set_secret(vault_url, name, secret_value)


if __name__ == "__main__":
    main()
