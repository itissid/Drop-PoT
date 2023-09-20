Setting up docker  instance for querying.

 docker run -it -e \
 PBF_PATH=/osm-maps/data/new-york_new-york.osm.pbf \
 -p 8080:8080  \
 -v /Users/sid/workspace/drop/geodata/new-york_new-york.osm.pbf:/osm-maps/data/new-york_new-york.osm.pbf \
 --name sid-nomatim2 \   
 mediagis/nominatim:4.2

 How to reverse geocode?
 TODO: Call the API on docker and test the reverse geocoding results.