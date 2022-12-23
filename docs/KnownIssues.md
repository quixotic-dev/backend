# Known Issues
We're aware of the following issues with Quix:

* The biggest scaling bottleneck for Quix is the PostgresDB and the Django ORM. One web request, can trigger dozens or
hundreds of SQL queries. Be careful not to have too many joins or n+1 queries when creating a new endpoint. It's 
recommended to use the [Django Debug Toolbar](https://django-debug-toolbar.readthedocs.io/en/latest/) and an APM like
[Scout](https://scoutapm.com/) or [Datadog](https://www.datadoghq.com/) to understand performance.
* Lack of authentication on a per user basis (for example using JSON Web Tokens) means that a malicious actor can 
update liked and hidden tokens on behalf of other users. In this scenario, the malicious actor cannot actually tamper
with anything of economic value.
* Because we index all NFTs on L2, we can index NFTs where the metadata is malicious javascript code. We attempt to
sanitize metadata, but it's likely possible to inject some malicious javascript into an NFT page or collection page.
