#  MIT License
#
#  Copyright (c) 2024. Patrick Brammerloo, Mark Zijdemans, DirectVPS [https://directvps.nl/]
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
import ipaddress

import settings
keystone = settings.keystone
cinder = settings.cinder
nova = settings.nova
neutron = settings.neutron


def get_keystone():
    try:
        mykeystoneprojects = keystone.projects.list()  # An admin-only API call
        tenant_dictionary = gettenants(mykeystoneprojects)  # We fetch Tenant information
        print(f"Fetched Tenant information as an admin")
        return tenant_dictionary
    except Exception as e:
        if "You are not authorized to perform the requested action: identity:list_projects" in str(e):
            print(f"Fetching Tenants failed. We will attempt Keystone calls per Instance instead")
            tenant_dictionary = "none"
            return tenant_dictionary
            # We sys.exit in parse_vm.py, because we should at least be able to fetch information,
            # by doing a Keystone call per Instance instead.
        else:
            print(f"Unable to collect Tenant information \n{e}")
            sys.exit(1)


def get_nova():
    try:
        # We try to fetch information from Nova with an admin-only API call
        myinstances = nova.servers.list(search_opts={'all_tenants': 1})
        print(f"Fetched Instance information as an admin")
    except Exception as e:
        if "Policy doesn't allow os_compute_api:servers:detail:get_all_tenants" in str(e):
            # On an Exception, We try to fetch information from Nova with a regular user API call
            print(f"Fetching Instances failed: {e}\nFetching Instance information as a regular user")
            myinstances = nova.servers.list()
            print(f"Fetched OpenStack Instance information as a regular user")
        else:
            print(f"Unable to collection Instance information \n{e}")
            sys.exit(1)
    try:
        # We fetch Flavor information using a semi-admin API call
        myflavors = nova.flavors.list(is_public=None)
        flavordictionary = getflavor(myflavors)
        print(f"Fetched Flavor information as an admin")
    except Exception as e:
        try:
            # On an Exception, We try to fetch Flavor information from Nova with a regular user API call
            print(f"Fetching Nova Flavors failed. {e}\n Attempting to collect Flavor information as a regular user \n\n")
            myflavors = nova.flavors.list()
            flavordictionary = getflavor(myflavors)
            print(f"Fetched Flavor information as a regular user")
        except Exception as e:
            print(f"Unable to collect Flavor information \n{e}")
            sys.exit(1)
    return myinstances, flavordictionary


def get_cinder():
    try:
        # We fetch Volume information using an admin-only API call
        cindervolumes = cinder.volumes.list(search_opts={'all_tenants': 1})
        cindervolumedictionary = getvolumes(cindervolumes)
        print(f"Fetched Cinder Volume information as an admin")
    except Exception as e:
        try:
            # On an Exception, We try to fetch Flavor information from Cinder with a regular user API call
            print(f"Fetching Cinder Volumes failed. Attempting to collect Volume information as a regular user")
            cindervolumes = cinder.volumes.list()
            cindervolumedictionary = getvolumes(cindervolumes)
            print(f"Fetched Cinder Volume information as a regular user")
        except Exception as e:
            print(f"Unable to collect Cinder Volume information \n{e}")
            sys.exit(1)
    return cindervolumedictionary


def get_neutron():
    try:
        # We attempt to collect information from Neutron for existing DHCP-agents
        neutronagents = neutron.list_agents()  # Empty result if regular user is used
        neutronagents = neutronagents['agents']
        neutron_dhcp_agent_dictionary = parse_dhcpagents(neutronagents)
        print(f"Fetched Neutron DHCP agent information")
    except Exception as e:
        print(f"Unable to collect Neutron DHCP agent information \n{e}")
        sys.exit(1)
    try:
        # We attempt to collect information from Neutron for Interfaces used for pretty much anything, except Float-IPs
        neutronports = neutron.list_ports()
        neutronports = neutronports['ports']
        neutroninterfacedictionary = getinterfaces(neutronports, neutron_dhcp_agent_dictionary)
        # We pass along the neutron agent dictionary to perform ID-substitution
        print(f"Fetched Neutron interface information")
    except Exception as e:
        print(f"Unable to collect Neutron interface information \n{e}")
        sys.exit(1)
    try:
        # We attempt to collect information from Neutron for all Networks available to this user
        neutronlistnetworks = neutron.list_networks()
        neutronlistnetworks = neutronlistnetworks['networks']
        neutronnetworkdictionary = getneutronnetworks(neutroninterfacedictionary, neutronlistnetworks)
        print(f"Fetched Neutron network information")
    except Exception as e:
        print(f"Unable to collect Neutron network information \n{e}")
        sys.exit(1)
    try:
        # We attempt to collect information from Neutron for Interfaces used for pretty much anything, except Float-IPs
        neutronsubnets = neutron.list_subnets()
        neutronsubnets = neutronsubnets['subnets']
        neutronsubnetdictionary = getsubnets(neutronsubnets)
        # We pass along the neutron agent dictionary to perform ID-substitution
        print(f"Fetched Neutron subnet information")
    except Exception as e:
        print(f"Unable to collect Neutron subnet information \n{e}")
        sys.exit(1)
    try:
        # We attempt to collect information from Neutron for Floating IPs used by Nova available to this user
        # Although Neutron Interfaces were collected earlier, we use this API call because there's better information
        neutronfloatports = neutron.list_floatingips()
        neutronfloatports = neutronfloatports['floatingips']
        neutronfloatdictionary = parsefloatips(neutronfloatports)
        print(f"Fetched Neutron Floating-IP information")
    except Exception as e:
        print(f"Unable to collect Neutron FLoating-IP information \n{e}")
        sys.exit(1)
    try:
        # We attempt to collect information from Neutron for Routers available to this user
        neutronrouters = neutron.list_routers()
        neutronrouters = neutronrouters["routers"]
        neutronrouterdictionary = parserouters(neutronrouters)
        print(f"Fetched Neutron Router information")
    except Exception as e:
        print(f"Unable to collect fetch Neutron Router information \n{e}")
        sys.exit(1)
    return neutroninterfacedictionary, neutronnetworkdictionary, neutronfloatdictionary, neutronrouterdictionary, neutron_dhcp_agent_dictionary, neutronsubnetdictionary


def getflavor(myflavors):
    flavordictionary = {}
    for flavor in myflavors:
        flavordictionary[flavor.id] = {'name': flavor.name, 'id': flavor.id, 'vcpu': flavor.vcpus, 'ram': flavor.ram,
                                       'swap': flavor.swap, 'disk': flavor.disk, 'ephemeral': flavor.ephemeral, }
        if flavordictionary[flavor.id]['swap'] == "":
            # For some reason OpenStack, sets Swap to "" instead of 0, when it is undefined
            flavordictionary[flavor.id]['swap'] = 0
    return flavordictionary


def getvolumes(mycindervolumes):
    try:
        volumedictionary = {}
        for volume in mycindervolumes:
            if volume.attachments:
                try:
                    # We keep only the results which are attached to an Instance
                    volumeid = volume.id
                    volumename = volume.name
                    volumesizegib = volume.size
                    volumesizegb = int(round(volumesizegib * 1.073742))
                    volumesizemb = int(round(volumesizegib * 1073.742))
                    volumeinstanceid = volume.attachments[0]['server_id']
                    if volumename == "" or volumename is None:
                        # OpenStack returns a "" or Null value when name is not set explicitly, so set name to the ID in that case
                        volumename = volume.id
                    volumename = volumename[:64]
                    volumedictionary[volumeid] = {'osvolname': volumename, 'osvolid': volumeid, 'osvolsizegb': volumesizegb,
                                                  'osvolinstanceid': volumeinstanceid, 'osvolsizemb': volumesizemb}
                except Exception as e:
                    print(f"Unable to create Cinder Volume for {volume} \n{e}")
                    sys.exit(1)
            else:
                continue
    except Exception as e:
        print(f"Unable to create Cinder Volume dictionary \n{e}")
        sys.exit(1)
    return volumedictionary


def parse_dhcpagents(neutronagents):
    myagentdictionary = {}
    for agent in neutronagents:
        try:
            if agent['agent_type'] == "DHCP agent":
                myagentdictionary[agent['id']] = {'hostname': agent['host'], 'id': agent['id']}
        except Exception as e:
            print(f"Error: {e} \n Unable to create Neutron DHCP agent dictionary for {agent}")
            sys.exit(1)
    return myagentdictionary


def getinterfaces(neutronports, agentdictionary):
    # We create a pretty and compacted dictionary, based on contents fetched from Neutron Interfaces API call
    myneutrondictionary = {}
    try:
        for interface in neutronports:
            if (interface['device_owner'] is not None and interface['device_owner'] != "" and
                    interface['device_id'] is not None and interface['device_id'] != ""):
                osifdeviceowner = interface['device_owner']
                # device_owner is the object attached to the interface: instance/router/Floating port ID
                # Examples: compute:nova, network:dhcp, network:router_gateway
            else:
                continue
            if (osifdeviceowner == 'compute:nova' or
                osifdeviceowner == 'network:router_gateway' or
                osifdeviceowner == 'network:ha_router_replicated_interface' or
                osifdeviceowner == 'network:router_ha_interface' or
                osifdeviceowner == 'network:dhcp'):
                # TODO Octavia (Load Balancer itself), Trove and or others as an owner
                # First we filter for interfaces that are actively used by wanted owners/services
                osifid = interface['id']
                osifname = interface['name']
                osifstatus = interface['status']
                osifmac = interface['mac_address']
                osifnetwork = interface['network_id']
                if interface['fixed_ips']:
                    interfaceip = interface['fixed_ips'][0]['ip_address']
                    # Only if there is an IP-adres whatsoever, we continue
                    if ipaddress.ip_address(interfaceip).is_loopback or ipaddress.ip_address(interfaceip).is_link_local:
                        # We skip IP-address that are APIPA or loopback
                        continue
                    elif ipaddress.ip_address(interfaceip).is_global:
                        # We keep interfaces that have a Global address regardless of for what purpose it is used
                        osifips = interface['fixed_ips']
                    elif (ipaddress.ip_address(interfaceip).is_private and (osifdeviceowner == 'compute:nova'
                                                                            or osifdeviceowner == 'network:router_gateway')):
                        # We keep private Nova and router addresses, to build a relevant view of the private network
                        osifips = interface['fixed_ips']
                    else:
                        # Anything left will provide NetBox noisy data, so we ignore it
                        continue
                elif not interface['fixed_ips']:
                    # We ignore any interface that doesn't have an IP-adress
                    # We explicitly print this because this is kinda weird for your OpenStack environment
                    print(f"Skipping Interface {osifid} as it contains no IP-addresses")
                    continue
                if osifdeviceowner == 'network:dhcp' and agentdictionary:
                    # DHCP interfaces don't bind to anything with an actual ID, so we bind them to the Neutron servers instead
                    for agent in agentdictionary:
                        if agentdictionary[agent]['hostname'] == interface['binding:host_id']:
                            osifdeviceid = agentdictionary[agent]['id']
                        else:
                            # Neutron agents API call is only available to admins
                            # If the Neutron server wasn't found in agentdictionary, we skip the DHCP-interface in question
                            continue
                elif osifdeviceowner == 'network:dhcp' and not agentdictionary:
                    # Agentdictionary should be empty if a regular user is used for fetching Neutron server names
                    # We simply skip adding the DHCP-interface if the dictionary was not populated
                    print(f"Skipping DHCP Interface {osifid} as we do not have permission to find out about Neutron servers")
                    continue
                elif osifdeviceowner:
                    osifdeviceid = interface['device_id']
                else:
                    # We skip anything that does not have an owner, that we didn't already overrule earlier
                    continue
                if osifname == '':
                    # Set osifname to osifid if there is no name set
                    osifname = osifid
                myneutrondictionary[osifid] = {'interfacemac': osifmac, 'interfaceid': osifid,'interfacename': osifname,
                                               'interfacestatus': osifstatus, 'interfaceassociation': osifdeviceid,
                                               'interfacenetwork': osifnetwork, 'interfaceips': osifips, 'osifdeviceowner': osifdeviceowner}
            else:
                continue
    except Exception as e:
        print(f"Unable to create Neutron interface dictionary \n{e}")
        sys.exit(1)
    return myneutrondictionary


def getneutronnetworks(neutronintdic, neutronlistnetworks):
    myneutronnetworks = {}
    # First we create a dictionary containing all OpenStack VRFs
    try:
        for network in neutronlistnetworks:
            osnetworkid = network['id']
            osnetworkname = network['name']
            if network['name'] == "" or network['name'] is None:
                # Neutron returns an empty name, if Network name was not set
                # So in this conditional we fill the name field with its ID instead
                osnetworkname = network['id']
            osnetworksubnets = network['subnets']
            myneutronnetworks[osnetworkid] = {'networkid': osnetworkid, 'networkname': osnetworkname,
                                                'networksubnets': osnetworksubnets }
    except Exception as e:
        print(f"Unable to create Neutron network dictionary \n{e}")
        sys.exit(1)
    # Private addresses should go in VRFs, to not contaminate your NetBox environment
    # So we compare to our dictionary of interfaces, for private IP-addresses in OpenStack networks
    # Global addresses will be added to the Global VRF
    openstack_vrf_dic = {}
    try:
        for portid in neutronintdic:
            for ip in neutronintdic[portid]['interfaceips']:
                openstackip = ip['ip_address']
                # For each interface in our dictionary we grab the IPs
                if ipaddress.ip_address(openstackip).is_private:
                    # If said IP is private, we grab the associated network-ID and its name and put it in our dictionary
                    openstacknetworkid = neutronintdic[portid]['interfacenetwork']  # First fetch the ID
                    openstacknetworkname = myneutronnetworks[openstacknetworkid]['networkname']  # Use the ID to fetch the name
                    openstack_vrf_dic[openstacknetworkid] = openstacknetworkname  # Filtered down to OS networks with private IPs
                else:
                    continue
    except Exception as e:
        print(f"Unable to define OpenStack networks that should be created as VRFs \n{e}")
        sys.exit(1)
    return openstack_vrf_dic


def getsubnets(neutron_subnets):
    openstack_subnet_dic = {}
    try:
        for subnet in neutron_subnets:
            cidr = ipaddress.ip_network(subnet['cidr'])
            prefix = cidr.prefixlen
            subnetname = subnet['name']
            if subnetname == "" or subnetname is None:
                # OpenStack returns a "" or Null value when name is not set explicitly, so set name to the ID in that case
                subnetname = subnet['id']
            else:
                pass
            openstack_subnet_dic[subnet['id']] = {'subnet_id': subnet['id'],
                                                  'subnet_name': subnetname,
                                                  'subnet_network_id': subnet['network_id'],
                                                  'subnet_cidr': subnet['cidr'],
                                                  'subnet_prefix': prefix
                                                 }
    except Exception as e:
        print(f"Unable to define OpenStack networks that should be created as VRFs \n{e}")
        sys.exit(1)
    return openstack_subnet_dic


def parsefloatips(floatports):
    # We create a pretty and compacted dictionary, based on contents fetched from the Neutron Floating IP API call
    myneutronfloatdictionary = {}
    for osfloat in floatports:
        try:
            if osfloat['port_id'] is not None and osfloat['fixed_ip_address'] is not None and osfloat["port_details"]["device_owner"] == "compute:nova":
                # Keep only that which is bound to an Instance and Interface, and only if said interface has an IP
                osfloatid = osfloat['id']
                osinstanceinterfaceid = osfloat['port_id']  # Interface it is bound to!
                osfloatintinstanceid = osfloat["port_details"]["device_id"]  # OpenStack Instance it is bound to
                osfloatintnetworkid = osfloat["port_details"]["network_id"]  # OpenStack network the internal IP is in
                osfloatinstanceintip = osfloat['fixed_ip_address']  # IP it is bound to
                osfloatip = osfloat['floating_ip_address']
                myneutronfloatdictionary[osfloatid] = {'floatid': osfloatid, 'floatip': osfloatip,
                                                       'boundtointerfaceid': osinstanceinterfaceid,
                                                       'boundtoip': osfloatinstanceintip,
                                                       'boundtoinstanceid': osfloatintinstanceid,
                                                       'boundtonetworkid': osfloatintnetworkid}
            else:
                pass
        except Exception as e:
            print(f"Unable to create Floating IP dictionary for Floating IP {osfloat} \n{e}")
            sys.exit(1)
    return myneutronfloatdictionary


def parserouters(neutronrouters):
    myrouterdictionary = {}
    for router in neutronrouters:
        try:
            if router['name'] != "" and router['name'] is not None:
                # Neutron returns an empty name, if router name was not set
                # So in this conditional we fill the name field with its ID instead
                osroutername = router['name']
            elif router['name'] == "" or router['name'] is None:
                osroutername = router['id']
            else:
                print(f"Unexpected error happened while setting the Name variable of the router dictionary")
                sys.exit(1)
            os_router_flavor_id = "Nothing"  # Normal router does not have a flavor, but can potentially be configured
            myrouterdictionary[router['id']] = {'name': osroutername, 'id': router['id'], 'status': router['status'],
                                                'flavorid': os_router_flavor_id, 'tenantid': router['tenant_id']}
        except Exception as e:
            print(f"Error: {e} \n Unable to create router dictionary for {router}")
            sys.exit(1)
    return myrouterdictionary


def gettenants(mykeystoneprojects):
    mytenantdictionary = {}
    for tenant in mykeystoneprojects:
        mytenantdictionary[tenant.id] = {'name': tenant.name, 'id': tenant.id}
    return mytenantdictionary

