launchpad_smart_contract_schema = {
    "title": "Smart Contract Specs",
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "The name of the NFT collection",
        },
        "symbol": {
            "type": "string",
            "description": "The symbol of the NFT collection",
        },
        "maxTokens": {
            "type": "number",
            "description": "The max number of tokens available.",
        },
        "greenList": {
            "type": "object",
            "description": "Whether this smart contract has a greenlist.",
            "properties": {
                "priceInWei": {
                    "type": "number",
                    "description": "This is the greenlist mint price in wei"
                },
                "maxMintPerAddress": {
                    "type": "number",
                    "description": "The max number of NFTs allowed to be minted per address",
                }
            },
            "required": ["priceInWei", "maxMintPerAddress"]
        },
        "publicMint": {
            "type": "object",
            "properties": {
                "priceInWei": {
                    "type": "number",
                    "description": "This is the mint price in wei"
                },
                "maxMintPerAddr": {
                    "type": "number",
                    "description": "The max allowed to be minted per address"
                }
            },
            "required": ["priceInWei", "maxMintPerAddr"]
        },
        "reserveTokens": {
            "type": "boolean",
            "description": "Whether this smart contract has a reserve mint function.",
       }
    },
    "required": [
        "name",
        "symbol",
        "maxTokens"
    ]
}
