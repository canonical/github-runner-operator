import subprocess
import logging
import json
from time import sleep

import boto3


if __name__ == "__main__":
    print("Wait for 60 seconds")
    sleep(60)
    print("Setting up microceph")
    subprocess.run(["sudo", "snap", "install", "microceph"], check=True)
    subprocess.run(["sudo", "microceph", "cluster", "bootstrap"], check=True)
    subprocess.run(["sudo", "microceph", "disk", "add", "loop,4G,3"], check=True)
    subprocess.run(["sudo", "microceph", "enable", "rgw"], check=True)
    output = subprocess.run(
        [
            "sudo",
            "microceph.radosgw-admin",
            "user",
            "create",
            "--uid",
            "test",
            "--display-name",
            "test",
        ],
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout
    key = json.loads(output)["keys"][0]
    key_id = key["access_key"]
    secret_key = key["secret_key"]
    print("Creating microceph bucket")
    boto3.client(
        "s3",
        endpoint_url="http://localhost",
        aws_access_key_id=key_id,
        aws_secret_access_key=secret_key,
    ).create_bucket(Bucket="test")
    print("Set up microceph")