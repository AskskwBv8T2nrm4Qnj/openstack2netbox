#  MIT License
#
#  Copyright (c) 2025. Patrick Brammerloo, Mark Zijdemans, DirectVPS [https://directvps.nl/]
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.

import os
import sys

from dotenv import load_dotenv
from dotenv import find_dotenv

# OpenStacks' authentication modules
from keystoneauth1.identity import v3
from keystoneauth1 import session

import pynetbox

# load variables from .env file
env_file = find_dotenv(filename='.openstack.env', usecwd=True)
load_dotenv(env_file)

netbox_token = os.getenv("netbox_token")
netbox_domain = os.getenv("netbox_domain")
cluster_name = os.getenv("cluster_name")
cluster_type = os.getenv("cluster_type_name")

os_auth_url = os.getenv("os_auth_url")
os_auth_url_type = os.getenv("os_auth_url_type")
os_username = os.getenv("os_username")
os_password = os.getenv("os_password")
os_user_domain_id = os.getenv("os_user_domain_id")
os_project_name = os.getenv("os_project_name")
os_project_domain_id = os.getenv("os_project_domain_id")


try:
    # Connect to Netbox
    nb = pynetbox.api(
        netbox_domain, token=netbox_token, threading=True
    )
    try:
        # Check whether required Netbox resources exist and are unique
        myclusterid = nb.virtualization.clusters.get(name=cluster_name).id
        nb.virtualization.cluster_types.get(name=cluster_type).id
        nb.extras.custom_fields.get(name="openstack_id").id
        nb.extras.custom_fields.get(name="openstack_hypervisor").id
        nb.extras.custom_fields.get(name="openstack_tenant").id
        nb.extras.custom_fields.get(name="openstack_flavor").id
        nb.extras.custom_fields.get(name="openstack_swap").id
        nb.extras.custom_fields.get(name="openstack_ephemeral").id
        nb.extras.custom_fields.get(name="openstack_interfaceid").id
        nb.extras.custom_fields.get(name="openstack_networkid").id
        nb.extras.custom_fields.get(name="openstack_volumeid").id
        nb.extras.custom_fields.get(name="openstack_subnetid").id
        netboxtagopenstackapiscriptid = nb.extras.tags.get(slug="openstack-api-script").id
    except Exception as e:
        if "Token expired" in str(e):
            print(f"The supplied Netbox user has its token expired: \n{e}")
            sys.exit(1)
        elif "The request failed with code 403 Forbidden" in str(e):
            print(f"The supplied Netbox user does not have access to Netbox: \n{e}")
            sys.exit(1)
        else:
            print(f"Expected Netbox resources were not found or are not unique enough to identify. Did you create the required prerequisites? \n{e}")
            sys.exit(1)
except Exception as e:
    print(f"Unable to connect to Netbox \n{e}")
    sys.exit(1)

if os_auth_url_type == "public":
    keystoneendpoint = "public"
    novaendpoint = "publicURL"
    cinderendpoint = "publicURL"
    neutronendpoint = "publicURL"
elif os_auth_url_type == "internal":
    keystoneendpoint = "internal"
    novaendpoint = "internalURL"
    cinderendpoint = "internalURL"
    neutronendpoint = "internalURL"
elif os_auth_url_type != "public" or os_auth_url_type != "internal":
    print(f"os_auth_url_type was not set to 'public' or 'internal'")
    sys.exit(1)

# Create object to establish OpenStack sessions with
auth = v3.Password(auth_url=os_auth_url, username=os_username,
                   password=os_password, project_name=os_project_name,
                   user_domain_id=os_user_domain_id, project_domain_id=os_project_domain_id)

# Initialize all modules in a row, so sessions don't get overwritten
try:
    # Keystone client
    from keystoneclient import client
    sesis = session.Session(auth=auth)
    keystone = client.Client(session=sesis, interface=keystoneendpoint)
except Exception as e:
    print(f"Unable to authenticaticate with Keystone using the supplied credentials. \n{e}")
    sys.exit(1)


try:
    # Nova client
    from novaclient import client
    sess = session.Session(auth=auth)
    nova = client.Client(2.8, session=sess, endpoint_type=novaendpoint)
except Exception as e:
    print(f"Unable to authenticaticate with Nova using the supplied credentials. \n{e}")
    sys.exit(1)


try:
    # Cinder client
    from cinderclient import client
    sesder = session.Session(auth=auth)
    cinder = client.Client(3.6, session=sesder, endpoint_type=cinderendpoint)
except Exception as e:
    print(f"Unable to authenticaticate with Cinder using the supplied credentials. \n{e}")
    sys.exit(1)


try:
    # Neutron
    from neutronclient.v2_0 import client
    sesa = session.Session(auth=auth)
    neutron = client.Client(session=sesa, endpoint_type=neutronendpoint)
except Exception as e:
    print(f"Unable to authenticaticate with Neutron using the supplied credentials. \n{e}")
    sys.exit(1)
