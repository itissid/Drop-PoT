1. Get the data for US NE and filter it per the bounding box:
>> osmium extract --bbox -74.274008,40.528333,-73.311119,40.956549 -o nyc-jc-bayonne-hoboken-fortlee.latest.osm.pbf us-northeast-latest.osm.pbf

1.2.1. Get a bounding box going 
https://boundingbox.klokantech.com/
GeoJSON:
[[[-74.2740081486,40.528332549],[-74.218726583,40.658025671],[-74.1535438413,40.6448798646],[-74.0586575718,40.8623903899],[-73.9150905206,40.9185272664],[-73.3226701599,40.9565485106],[-73.311118788,40.5402472329],[-74.2740081486,40.528332549]]]

1.2.1. CSV: 
-74.274008,40.528333,-73.311119,40.956549

2. These are pbf files and then I used the following command to extact only the data I needed for transportation: 
osmium tags-filter "${INPUT_FILE}"     w/highway     w/footway     w/public_transport     w/railway=platform     w/aeroway=taxiway     w/aeroway=runway     n/place     n/addr:housenumber     n/addr:street     n/addr:city     n/addr:postcode     n/addr:country -o nyc-jc-bayonne-hoboken-fortlee-footway-2.latest.osm.pbf

Where INPUT_FILE is from the last step. Note that the command can output PBF files which were much smaller in size in my case. Next I copied it to 

https://linuxcommandlibrary.com/man/osmium

osm_extract_download --data-format=pbf --api-token ebd93fb9-daae-4b05-9973-0b15815281a6 new-york_new-york


Setting up docker  instance for querying.

 docker run -it -e \
 PBF_PATH=/osm-maps/data/new-york_new-york.osm.pbf \
 -p 8080:8080  \
 -v /Users/sid/workspace/drop/geodata/new-york_new-york.osm.pbf:/osm-maps/data/new-york_new-york.osm.pbf \
 --name sid-nomatim2 \   
 mediagis/nominatim:4.2

 How to reverse geocode?
 - See the main README there is a step there for it
 


# Setting up docker instance for Open Routing Service
(TODO): How can I consolidate this adhoc docker command and the image I deploy on k8s?
This is used to look up the routing information between two points on the map we extracted.
```
cd ~/workspace/openrouteservice/openrouteservice
docker compose up --build

```


# DON"T USE BELOW. INSTEAD USE docker compose up instead.
cd ~/workspace/openrouteservice/openrouteservice

mkdir -p docker/conf docker/elevation_cache docker/graphs docker/logs/ors docker/logs/tomcat
docker run -dt -u "${UID}:${GID}" \
  --name ors-app \
  -p 8080:8080 \
  -v $PWD/docker/graphs:/home/ors/ors-core/data/graphs \
  -v $PWD/docker/elevation_cache:/home/ors/ors-core/data/elevation_cache \
  -v $PWD/docker/logs/ors:/home/ors/ors-core/logs/ors \
  -v $PWD/docker/logs/tomcat:/home/ors/tomcat/logs \
  -v $PWD/docker/conf:/home/ors/ors-conf \
  -v /Users/sid/workspace/drop/geodata/new-york_new-york.osm.pbf:/home/ors/ors-core/data/osm_file.pbf \
  -e "BUILD_GRAPHS=True" \
  -e "JAVA_OPTS=-Djava.awt.headless=true -server -XX:TargetSurvivorRatio=75 -XX:SurvivorRatio=64 -XX:MaxTenuringThreshold=3 -XX:+UseG1GC -XX:+ScavengeBeforeFullGC -XX:ParallelGCThreads=4 -Xms1g -Xmx2g" \
  -e "CATALINA_OPTS=-Dcom.sun.management.jmxremote -Dcom.sun.management.jmxremote.port=9001 -Dcom.sun.management.jmxremote.rmi.port=9001 -Dcom.sun.management.jmxremote.authenticate=false -Dcom.sun.management.jmxremote.ssl=false -Djava.rmi.server.hostname=localhost" \
  openrouteservice/openrouteservice:latest
~~


How do we know its working correctly?  

- For the extract of Jersey city and
hoboken here is the curl command to check it(note the radiuses parameter is set
to -1 to indicate that we want the route to be calculated without any
restrictions):


 curl -X POST   'http://127.0.0.1:8080/ors/v2/directions/foot-walking'   -H 'Content-Type: application/json; charset=utf-8'   -H 'Accept: application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8'   -d '{"coordinates":[[-74.0358352661133, 40.741924698522084], [-74.04201353264135, 40.69859355]], "radiuses":[-1]}'