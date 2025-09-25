import requests
from openstack.connection import Connection

def test_openstack(openstack_connection: Connection):
    output_filename = "test.image"

    request = requests.get(
        "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img",
        timeout=60 * 20,
        stream=True,
    )  # nosec: B310, B113

    with open(output_filename, "wb") as file:
        for chunk in request.iter_content(1024 * 1024):  # 1 MB chunks
            file.write(chunk)

    openstack_connection.create_image(
        name="tmp_test",
        filename=output_filename,
        properties={"architecture": "amd64"},
        allow_duplicates=True,
        wait=True,
    )
