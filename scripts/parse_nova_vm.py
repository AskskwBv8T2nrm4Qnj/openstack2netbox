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

import sys
import re

from scripts.netbox.create import createnetboxvm
from scripts.netbox.update import updatenetboxvm
from scripts.openstack.checkstatus import getstatus

import settings
keystone = settings.keystone
nb = settings.nb
cluster_name = settings.cluster_name

unchangedvms = 0


def nova_to_netboxvms(myinstances, nova_dictionary, keystone_dictionary,  netbox_vm_dictionary):
    global unchangedvms
    for os_instance in myinstances:
        os_nova_vm = define_nova_object(os_instance, nova_dictionary, keystone_dictionary)
        try:
            # print(vars(os_nova_vm))
            if os_nova_vm.instance_id in netbox_vm_dictionary.keys() and os_nova_vm.custom_name in str(netbox_vm_dictionary.values()):
                # First we check for custom-named VMs we were forced to create, whenever there were duplicates
                # NetBox doesn't allow unique names per cluster, unless a Tenant was assigned to said VM
                netboxvm = netbox_vm_dictionary.get(os_nova_vm.instance_id)
                nb_vm = CreateNetboxVmObject(netboxvm)
                compare_vm_objects(os_nova_vm, nb_vm)
            elif os_nova_vm.instance_id in netbox_vm_dictionary.keys():
                netboxvm = netbox_vm_dictionary.get(os_nova_vm.instance_id)
                nb_vm = CreateNetboxVmObject(netboxvm)
                compare_vm_objects(os_nova_vm, nb_vm)
            elif (os_nova_vm.instance_id not in netbox_vm_dictionary.keys() and
                  os_nova_vm.name in str(netbox_vm_dictionary.values()) and
                    nb.virtualization.virtual_machines.get(name=os_nova_vm.name, cluster_name=cluster_name,
                                                              tag="openstack-api-script") is not None):
                # We're dealing with a new VM that may, or may not be, a replacement of an older VM
                # So we fetch the ID of said machine, based on the OpenStack name and then replace its values
                nbvm_fetch = nb.virtualization.virtual_machines.get(name=os_nova_vm.name, cluster_name=cluster_name,
                                                              tag="openstack-api-script")
                if nbvm_fetch.custom_fields["openstack_tenant"] == os_nova_vm.tenant:
                    # If there is a NB VM in the same NB cluster with the same OS VM-name + OS tenant,
                    # we will assume it is a replacement
                    # Notably, the passed instance.id will overwrite the 'old' OpenStack Instance ID field
                    # The next run, our second or first if statement should trigger for this specific Instance instead
                    nb_vm = CreateNetboxVmObject(nbvm_fetch)
                    compare_vm_objects(os_nova_vm, nb_vm)
                else:
                    # If the tenant is not equal, we create a new VM instead
                    createnetboxvm(os_nova_vm)
            else:
                # Finally we create the Netbox VM if we couldn't find or compare it to anything NetBox.
                createnetboxvm(os_nova_vm)
        except Exception as e:
            print(f"Unable to create or update VM {os_nova_vm.name} \n{e}")
            print(vars(os_nova_vm))
            sys.exit(1)
    print(f"Skipped {unchangedvms} VMS in total, because there were no changes.")


def define_nova_object(instance, flavordictionary, tenantdictionary):
    os_instance_flavorname = flavordictionary[instance.flavor['id']]['name']
    os_instance_flavorcpu = flavordictionary[instance.flavor['id']]['vcpu']
    os_instance_flavorram = flavordictionary[instance.flavor['id']]['ram']
    os_instance_flavorswap = flavordictionary[instance.flavor['id']]['swap']
    os_instance_flavordisk = flavordictionary[instance.flavor['id']]['disk']
    os_instance_flavorephemeral = flavordictionary[instance.flavor['id']]['ephemeral']
    custom_instance_name = instance.name[:53] + "_[" + instance.id[:8] + "]"
    instancename = instance.name[:64]
    try:
        instancetenant = tenantdictionary[instance.tenant_id]['name']  # We fetch Tenant name from our dictionary
    except Exception as e:
        if tenantdictionary == "none":
            # This is where we attempt fetching Keystone information for the last time
            # but only if collectopenstackinformation() didn't populate tenantdictionary properly
            try:
                instancetenant = keystone.projects.get(instance.tenant_id)  # We fetch Tenant name via Keystone call
                instancetenant = instancetenant.name
            except Exception as e:
                print(f"Unable to access OpenStack Keystone tenant name \n{e}")
                sys.exit(1)
        else:
            print(f"Unable to populate Keystone instancetenant variable for instance {instance} \n{e}")
            print("This Instance is likely associated with a Tenant that does not exist")
            instancetenant = "Not associated with a Tenant"
            # sys.exit(1)
    try:
        currentstatus = getstatus(instance.status)  # We transform OpenStack statusses to Netbox statusses
    except Exception as e:
        print(f"Unable to transform OpenStack status to Netbox status \n{e}")
        sys.exit(1)
    try:
        instancehypervisor = getattr(instance, 'OS-EXT-SRV-ATTR:host')  # Admin-only call/attribute
        if instancehypervisor is None:
            instancehypervisor = "Unknown"  # Shelved Instances cause instancehypervisor to be None
    except Exception as e:
        if str(e) == "OS-EXT-SRV-ATTR:host":  # If we can't get the hypervisor name, NB field will become "Unknown"
            instancehypervisor = "Unknown"
        else:
            print(f"Unable to fetch and or set instancehypervisor variable \n{e}")
            sys.exit(1)
    if instance.status == "ACTIVE":
        try:
            # Attempt to get hostname from console output, only if the Instance in a normal state
            consoleoutput = instance.get_console_output()  # Admin only call
            hostnamesearch = re.search(r'(.*)\s\blogin:\s', consoleoutput)
            try:
                hostname = re.sub(r'\s\blogin:\s', '', hostnamesearch.group(0))
            except Exception as e:
                if str(e) == "'NoneType' object has no attribute 'group'":
                    # If the regex finds no matches, we set the hostname to unknown
                    hostname = "unknown"
                else:
                    print(f"Unable to fetch hostname for {instance.name} \n{e}")
                    sys.exit(1)
        except Exception as e:
            if "Policy doesn't allow os_compute_api:os-console-output to be performed. (HTTP 403)" in str(e):
                # A non-admin was used to request this information, so we set the hostname to Unknown
                hostname = "unknown"
            else:
                print(f"Unable to get console-output for Instance {instance.name} \n{e}")
                sys.exit(1)
    else:
        # Console output won't be available for Instances that are shutoff/unavailable, so set hostname to unknown
        hostname = "unknown"
    nova_vm = CreateNovaVmObject(instancename, custom_instance_name, instance.id, instancetenant,
                                 currentstatus, instancehypervisor, hostname,
                                 os_instance_flavorname, os_instance_flavorcpu, os_instance_flavorram,
                                 os_instance_flavorswap, os_instance_flavordisk, os_instance_flavorephemeral)
    return nova_vm


class CreateNovaVmObject(object):
    def __init__(self, name, customname, instance_id, tenant, status, hypervisor, hostname,
                 flavorname, flavorcpu, flavorram, flavorswap, flavordisk, flavorephemeral):
        self.name = name
        self.custom_name = customname
        self.instance_id = instance_id
        self.tenant = tenant
        self.status = status
        self.hypervisor = hypervisor
        self.hostname = hostname
        self.flavorname = flavorname
        self.flavorcpu = int(flavorcpu)
        self.flavorram = int(flavorram)
        self.flavorswap = int(flavorswap)
        self.flavordisk = int(flavordisk)
        self.flavorephemeral = int(flavorephemeral)


class CreateNetboxVmObject(object):
    def __init__(self, dictionary):
        self.name = dictionary.name
        self.netbox_id = dictionary.id
        self.openstack_id = dictionary.custom_fields["openstack_id"]
        self.tenant = dictionary.custom_fields["openstack_tenant"]
        status = str(dictionary.status)
        status = status.lower()
        self.status = status
        self.hypervisor = dictionary.custom_fields["openstack_hypervisor"]
        self.hostname = dictionary.custom_fields["openstack_hostname"]
        self.flavorname = dictionary.custom_fields["openstack_flavor"]
        cpu = dictionary.vcpus
        self.flavorcpu = int(cpu)
        self.flavorram = dictionary.memory
        self.flavorswap = dictionary.custom_fields["openstack_swap"]
        self.flavordisk = dictionary.disk
        self.flavorephemeral = dictionary.custom_fields["openstack_ephemeral"]


def compare_vm_objects(os_nova_vm_obj, nb_vm_obj):
    global unchangedvms
    if os_nova_vm_obj.hostname != "unknown":
        pass
    elif nb_vm_obj.hostname != "unknown" and os_nova_vm_obj.hostname == "unknown":
        # After a certain amount of time, the hostname may become unavailable in the OpenStack console
        # If the NetBox side has a hostname set, we ignore the OpenStack value if it is our default of unknown
        os_nova_vm_obj.hostname = nb_vm_obj.hostname
    try:
        if ((nb_vm_obj.name != os_nova_vm_obj.name and nb_vm_obj.name != os_nova_vm_obj.custom_name) or
                nb_vm_obj.openstack_id != os_nova_vm_obj.instance_id or
                nb_vm_obj.tenant != os_nova_vm_obj.tenant or
                nb_vm_obj.status != os_nova_vm_obj.status or
                nb_vm_obj.hypervisor != os_nova_vm_obj.hypervisor or
                nb_vm_obj.hostname != os_nova_vm_obj.hostname or
                nb_vm_obj.flavorname != os_nova_vm_obj.flavorname or
                nb_vm_obj.flavorcpu != os_nova_vm_obj.flavorcpu or
                nb_vm_obj.flavorram != os_nova_vm_obj.flavorram or
                nb_vm_obj.flavorswap != os_nova_vm_obj.flavorswap or
                # We skip disk as it is defined by Virtual Disks
                nb_vm_obj.flavorephemeral != os_nova_vm_obj.flavorephemeral):
            #print(vars(os_nova_vm_obj))
            #print(vars(nb_vm_obj))
            updatenetboxvm(nb_vm_obj.netbox_id, os_nova_vm_obj)
        else:
            unchangedvms = unchangedvms + 1
            if (unchangedvms % 10) == 0:
                print(f"Skipped {unchangedvms} VMs because nothing changed")
            else:
                pass
            pass
    except Exception as e:
        print(f"Unable to compare OpenStack Instance to Netbox Virtual Machine:\n")
        print(f"{e}\n")
        print(f"{vars(os_nova_vm_obj)}\n")
        print(f"{vars(nb_vm_obj)}\n")
        sys.exit(1)
