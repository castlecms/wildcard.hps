.PHONY=start-opensearch
start-opensearch:
	docker run -p 9200:9200 -p 9600:9600 -e "discovery.type=single-node" -d opensearchproject/opensearch:latest

.PHONY=start-opensearch-with-nerdctl
start-opensearch-with-nerdctl:
	nerdctl run -p 9200:9200 -p 9600:9600 -e "discovery.type=single-node" -d opensearchproject/opensearch:latest
