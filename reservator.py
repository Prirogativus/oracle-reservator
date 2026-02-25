import os
import oci
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('oracle_ampere.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── .env VARIABLES ───────────────────────────────────────────
COMPARTMENT_ID      = os.getenv("COMPARTMENT_ID")
AVAILABILITY_DOMAIN = os.getenv("AVAILABILITY_DOMAIN")
SUBNET_ID           = os.getenv("SUBNET_ID")
IMAGE_ID            = os.getenv("IMAGE_ID")
SSH_PUBLIC_KEY      = os.getenv("SSH_PUBLIC_KEY")
INSTANCE_NAME   = os.getenv("INSTANCE_NAME", "ampere-free")
OCPUS           = float(os.getenv("OCPUS", "4"))
MEMORY_GB       = float(os.getenv("MEMORY_GB", "24"))
RETRY_INTERVAL  = int(os.getenv("RETRY_INTERVAL", "60"))
# ──────────────────────────────────────────────────────────────────────

def create_instance(compute_client):
    details = oci.core.models.LaunchInstanceDetails(
        compartment_id=COMPARTMENT_ID,
        availability_domain=AVAILABILITY_DOMAIN,
        display_name=INSTANCE_NAME,
        shape="VM.Standard.A1.Flex",
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=OCPUS,
            memory_in_gbs=MEMORY_GB
        ),
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            source_type="image",
            image_id=IMAGE_ID
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            subnet_id=SUBNET_ID,
            assign_public_ip=True
        ),
        metadata={
            "ssh_authorized_keys": SSH_PUBLIC_KEY
        }
    )
    return compute_client.launch_instance(details)

def main():
    config = oci.config.from_file()
    compute_client = oci.core.ComputeClient(config)
    
    attempt = 0
    logger.info("Starting the hunt for Ampere A1...")

    while True:
        attempt += 1
        try:
            logger.info(f"Attempt #{attempt}...")
            response = create_instance(compute_client)

            instance = response.data
            logger.info(f"SUCCESS! Instance created!")
            logger.info(f"   ID:     {instance.id}")
            logger.info(f"   State:  {instance.lifecycle_state}")
            logger.info(f"   Name:   {instance.display_name}")
            logger.info("Check Oracle Console to get the IP address")
            break

        except oci.exceptions.ServiceError as e:
            if e.status == 500 and "Out of capacity" in str(e.message):
                logger.warning(f"Out of Capacity. Next attempt in {RETRY_INTERVAL}s...")
            elif e.status == 429:
                logger.warning(f"Rate limit. Waiting 120s...")
                time.sleep(120)
                continue
            else:
                logger.error(f"API error: {e.status} - {e.message}")
                if e.status in [400, 401, 404]:
                    logger.error("Critical error, check your config. Stopping.")
                    break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        
        time.sleep(RETRY_INTERVAL)

if __name__ == "__main__":
    main()