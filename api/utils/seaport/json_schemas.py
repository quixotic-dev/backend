import jsonschema
eth_addr_regex = "^0x[a-fA-F0-9]{40}$"

# Sell orders
sell_order_offer_item_schema = {
    "title": "Sell Order Offer Item Schema",
    "type": "object",
    "properties": {
        "itemType": {
            "type": "number",
            "pattern": "2"
        },
        "token": {
            "type": "string",
            "pattern": eth_addr_regex
        },
        "identifierOrCriteria": {
            "type": "string"
        },
        "startAmount": {
            "type": "string",
            "pattern": "1",
        },
        "endAmount": {
            "type": "string",
            "pattern": "1"
        }
    },
    "required": [
        "itemType",
        "token",
        "identifierOrCriteria",
        "startAmount",
        "endAmount",
    ]
}

sell_order_offer_schema = {
    "title": "Sell Order Offer Schema",
    "type": "array",
    "items": sell_order_offer_item_schema,
    "minItems": 1,
    "maxItems": 1
}

sell_order_consideration_item_schema = {
    "title": "Sell Order Consideration Item Schema",
    "type": "object",
    "properties": {
        "itemType": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
        },
        "token": {
            "type": "string",
            "pattern": eth_addr_regex
        },
        "identifierOrCriteria": {
            "type": "string",
            "pattern": "0"
        },
        "startAmount": {
            "type": "string"
        },
        "endAmount": {
            "type": "string"
        },
        "recipient": {
            "type": "string",
            "pattern": eth_addr_regex
        }
    },
    "required": [
        "itemType",
        "token",
        "identifierOrCriteria",
        "startAmount",
        "endAmount",
        "recipient"
    ]
}

sell_order_consideration_schema = {
    "title": "Sell Order Consideration Schema",
    "type": "array",
    "items": sell_order_consideration_item_schema,
    "minItems": 2,
    "maxItems": 3
}

sell_order_parameters_schema = {
    "title": "Sell Order Parameters Schema",
    "type": "object",
    "properties": {
        "offerer": {
            "type": "string",
            "pattern": eth_addr_regex
        },
        "zone": {
            "type": "string",
            "pattern": eth_addr_regex
        },
        "zoneHash": {
            "type": "string",
        },
        "startTime": {
            "type": "string",
            "pattern": "[0-9]+"
        },
        "endTime": {
            "type": "string",
            "pattern": "[0-9]+"
        },
        "orderType": {
            "type": "number",
            "minimum": 0,
            "maximum": 3
        },
        "offer": sell_order_offer_schema,
        "consideration": sell_order_consideration_schema

    },
    "required": [
        "offerer",
        "zone",
        "zoneHash",
        "startTime",
        "endTime",
        "orderType",
        "offer",
        "consideration"
    ],
}

sell_order_schema = {
    "title": "Sell Order Schema",
    "type": "object",
    "properties": {
        "parameters": sell_order_parameters_schema,
        "signature": {
            "type": "string",
            "pattern": "^0x[a-fA-F0-9]+$"
        }
    },
    "required": [
        "parameters",
        "signature"
    ]
}

# Buy Order ERC721 Json Validation

buy_order_consideration_item_schema = {
    "title": "Buy Order Offer Item Schema",
    "type": "object",
    "properties": {
        "itemType": {
            "type": "number",
            "minimum": 1,
            "maximum": 1
        },
        "token": {
            "type": "string",
            "pattern": eth_addr_regex
        },
        "identifierOrCriteria" : {
            "type": "string",
            "pattern": "^0$"
        },
        "startAmount": {
            "type": "string",
            "pattern": "^[0-9]+$",
        },
        "endAmount": {
            "type": "string",
            "pattern": "^[0-9]+$"
        }
    },
    "required": [
        "itemType",
        "token",
        "identifierOrCriteria",
        "startAmount",
        "endAmount",
    ]
}

buy_order_offer_item_schema = {
    "title": "Buy Order Offer Item Schema",
    "type": "object",
    "properties": {
        "itemType": {
            "type": "number",
            "pattern": "^1$"
        },
        "token": {
            "type": "string",
            "pattern": eth_addr_regex
        },
        "identifierOrCriteria" : {
            "type": "string",
            "pattern": "^0$"
        },
        "startAmount": {
            "type": "string",
            "pattern": "^[0-9]+$",
        },
        "endAmount": {
            "type": "string",
            "pattern": "^[0-9]+$"
        }
    },
}

buy_order_offer_schema = {
    "title": "Buy Order Offer Schema",
    "type": "array",
    "items": buy_order_offer_item_schema,
    "minItems": 1,
    "maxItems": 1
}

buy_order_consideration_item_schema = {
    "title": "Buy Order Consideration Item Schema",
    "type": "object",
    "properties": {
        "itemType": {
            "type": "number",
            "minimum": 1,
            "maximum": 3
        },
        "token": {
            "type": "string",
            "pattern": eth_addr_regex
        },
        "identifierOrCriteria": {
            "type": "string",
            "pattern": "^[0-9]+$"
        },
        "startAmount": {
            "type": "string",
        },
        "endAmount": {
            "type": "string",
        },
        "recipient": {
            "type": "string",
            "pattern": eth_addr_regex
        }
    },
    "required": [
        "itemType",
        "token",
        "identifierOrCriteria",
        "startAmount",
        "endAmount",
        "recipient"
    ]
}

buy_order_consideration_schema = {
    "title": "Sell Order Consideration Schema",
    "type": "array",
    "items": buy_order_consideration_item_schema,
    "minItems": 2,
    "maxItems": 3
}

buy_order_parameters_schema = {
    "title": "Buy Order Parameters Schema",
    "type": "object",
    "properties": {
        "offerer": {
            "type": "string",
            "pattern": eth_addr_regex
        },
        "zone": {
            "type": "string",
            "pattern": eth_addr_regex
        },
        "zoneHash": {
            "type": "string",
        },
        "startTime": {
            "type": "string",
            "pattern": "[0-9]+"
        },
        "endTime": {
            "type": "string",
            "pattern": "[0-9]+"
        },
        "orderType": {
            "type": "number",
            "minimum": 2,
            "maximum": 3
        },
        "offer": buy_order_offer_schema,
        "consideration": buy_order_consideration_schema

    },
    "required": [
        "offerer",
        "zone",
        "zoneHash",
        "startTime",
        "endTime",
        "orderType",
        "offer",
        "consideration"
    ],
}

buy_order_schema = {
    "title": "Buy Order Schema",
    "type": "object",
    "properties": {
        "parameters": buy_order_parameters_schema,
        "signature": {
            "type": "string",
            "pattern": "^0x[a-fA-F0-9]+$"
        }
    },
    "required": [
        "parameters",
        "signature"
    ]
}

