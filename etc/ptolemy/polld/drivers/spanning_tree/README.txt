spannign tree


iterative definition does not lookup key name for goup_by_key


netconfig: 
- add mac address peers (neighbour group)
- add port group

root: 
- need index?-
- rename physical port to designated_port
- remove root_port
- add is_root 
-- if physical_port == 0, then is root or root_cost == 0
-- generic.yaml, has root_port; convert to designated_port

port
- filter out non-local mac addresses? how?

