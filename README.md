# ptolemy
ptolemy is a metrics collection and storage framework. Whilst focused on network meta and timeseries, it has an extensible plugin architecture for collecting new specifications and groupings of metrics and uses pub/sub to faciliate the storage and analysis of the data.

# Overview
A scheduler is used to determine what to query and pollers utilise YAML based drivers to collect data via SNMP or CLI scrapers. Drivers are generically written such that autodiscovery of drivers can be performed. Each specification (a driver defining what kind of data is it gathering, eg cpu, memory, port utilisation etc) may have one or many groups (a logical grouping of metrics). As there is no assumption of the data format of content of the metrics, ptolemy is equally suited to collect meta (querying ARP, CAM, spanning tree, CDP/LLDP, module serial numbers etc) as well as time series data (number of wireless users, interface statistics, temperatures etc).

As there is a clean separation between data collection and data storage, we are free to pick and mix storage backends for different specification/groups. For example, meta data would better suited for a real database like postgres or mysql, whilst time series data is stored in graphite or influxdb. In addition, as the mechanism between data gathering and storage is pub/sub (currently using rabbitmq) one may attach multiple storage mechanisms for the same specification. A typical case would be that time series data may also be duplicated into a key-value cache like redis for dashboards or sent to an analysis backend to alert on say if the utilisation of an uplink is greater than an arbitary threshold.

# Features
- automatic discovery of device features and mapping to drivers
- customisable schedules per device or grouping of devices (eg collect ARP tables from core routers less frequently than edge routers, or just don't collect CAM tables from a specific department)
- postgres, redis, graphite and influxdb storage
- topology discovery and storage (layer 1 via cdp/lldp, layer 2 via spanning trees and layer 3 via route tables)
- gather data via SNMP or Command Line scrapers
- extend metrics to poll for via simple YAML files
- horizontally scalable architecture for entire architecture

# GUI
please see ptolemy-web for a rails based frontend.

# Usage
