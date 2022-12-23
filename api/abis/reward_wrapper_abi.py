import json

reward_wrapper_abi = json.loads("""
[
    {
      "inputs": [],
      "stateMutability": "nonpayable",
      "type": "constructor"
    },
    {
      "anonymous": false,
      "inputs": [
        {
          "indexed": true,
          "internalType": "address",
          "name": "caller",
          "type": "address"
        },
        {
          "indexed": false,
          "internalType": "uint256",
          "name": "amount",
          "type": "uint256"
        }
      ],
      "name": "ETHWithdrawn",
      "type": "event"
    },
    {
      "anonymous": false,
      "inputs": [
        {
          "indexed": false,
          "internalType": "uint8",
          "name": "version",
          "type": "uint8"
        }
      ],
      "name": "Initialized",
      "type": "event"
    },
    {
      "anonymous": false,
      "inputs": [
        {
          "indexed": true,
          "internalType": "address",
          "name": "owner",
          "type": "address"
        },
        {
          "indexed": true,
          "internalType": "address",
          "name": "cancelledPotentialOwner",
          "type": "address"
        }
      ],
      "name": "OwnershipTransferCancelled",
      "type": "event"
    },
    {
      "anonymous": false,
      "inputs": [
        {
          "indexed": true,
          "internalType": "address",
          "name": "previousOwner",
          "type": "address"
        },
        {
          "indexed": true,
          "internalType": "address",
          "name": "newOwner",
          "type": "address"
        }
      ],
      "name": "OwnershipTransferFinalized",
      "type": "event"
    },
    {
      "anonymous": false,
      "inputs": [
        {
          "indexed": true,
          "internalType": "address",
          "name": "owner",
          "type": "address"
        },
        {
          "indexed": true,
          "internalType": "address",
          "name": "potentialOwner",
          "type": "address"
        }
      ],
      "name": "OwnershipTransferInitiated",
      "type": "event"
    },
    {
      "anonymous": false,
      "inputs": [
        {
          "indexed": false,
          "internalType": "address",
          "name": "account",
          "type": "address"
        }
      ],
      "name": "Paused",
      "type": "event"
    },
    {
      "anonymous": false,
      "inputs": [
        {
          "indexed": true,
          "internalType": "address",
          "name": "rewardDeriver",
          "type": "address"
        }
      ],
      "name": "RewardDeriverSet",
      "type": "event"
    },
    {
      "anonymous": false,
      "inputs": [
        {
          "indexed": true,
          "internalType": "address",
          "name": "rewardReceiver",
          "type": "address"
        },
        {
          "indexed": false,
          "internalType": "uint256",
          "name": "rewardAmountInOP",
          "type": "uint256"
        },
        {
          "indexed": true,
          "internalType": "bytes32",
          "name": "campaignId",
          "type": "bytes32"
        },
        {
          "indexed": false,
          "internalType": "string",
          "name": "campaignString",
          "type": "string"
        }
      ],
      "name": "RewardSent",
      "type": "event"
    },
    {
      "anonymous": false,
      "inputs": [
        {
          "indexed": false,
          "internalType": "address",
          "name": "account",
          "type": "address"
        }
      ],
      "name": "Unpaused",
      "type": "event"
    },
    {
      "inputs": [],
      "name": "acceptOwnershipTransfer",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "cancelOwnershipTransfer",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [
        {
          "components": [
            {
              "components": [
                {
                  "internalType": "address",
                  "name": "offerer",
                  "type": "address"
                },
                {
                  "internalType": "address",
                  "name": "zone",
                  "type": "address"
                },
                {
                  "components": [
                    {
                      "internalType": "enum ItemType",
                      "name": "itemType",
                      "type": "uint8"
                    },
                    {
                      "internalType": "address",
                      "name": "token",
                      "type": "address"
                    },
                    {
                      "internalType": "uint256",
                      "name": "identifierOrCriteria",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "startAmount",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "endAmount",
                      "type": "uint256"
                    }
                  ],
                  "internalType": "struct OfferItem[]",
                  "name": "offer",
                  "type": "tuple[]"
                },
                {
                  "components": [
                    {
                      "internalType": "enum ItemType",
                      "name": "itemType",
                      "type": "uint8"
                    },
                    {
                      "internalType": "address",
                      "name": "token",
                      "type": "address"
                    },
                    {
                      "internalType": "uint256",
                      "name": "identifierOrCriteria",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "startAmount",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "endAmount",
                      "type": "uint256"
                    },
                    {
                      "internalType": "address payable",
                      "name": "recipient",
                      "type": "address"
                    }
                  ],
                  "internalType": "struct ConsiderationItem[]",
                  "name": "consideration",
                  "type": "tuple[]"
                },
                {
                  "internalType": "enum OrderType",
                  "name": "orderType",
                  "type": "uint8"
                },
                {
                  "internalType": "uint256",
                  "name": "startTime",
                  "type": "uint256"
                },
                {
                  "internalType": "uint256",
                  "name": "endTime",
                  "type": "uint256"
                },
                {
                  "internalType": "bytes32",
                  "name": "zoneHash",
                  "type": "bytes32"
                },
                {
                  "internalType": "uint256",
                  "name": "salt",
                  "type": "uint256"
                },
                {
                  "internalType": "bytes32",
                  "name": "conduitKey",
                  "type": "bytes32"
                },
                {
                  "internalType": "uint256",
                  "name": "totalOriginalConsiderationItems",
                  "type": "uint256"
                }
              ],
              "internalType": "struct OrderParameters",
              "name": "parameters",
              "type": "tuple"
            },
            {
              "internalType": "bytes",
              "name": "signature",
              "type": "bytes"
            }
          ],
          "internalType": "struct Order[]",
          "name": "orders",
          "type": "tuple[]"
        },
        {
          "components": [
            {
              "internalType": "uint256",
              "name": "orderIndex",
              "type": "uint256"
            },
            {
              "internalType": "uint256",
              "name": "itemIndex",
              "type": "uint256"
            }
          ],
          "internalType": "struct FulfillmentComponent[][]",
          "name": "offerFulfillments",
          "type": "tuple[][]"
        },
        {
          "components": [
            {
              "internalType": "uint256",
              "name": "orderIndex",
              "type": "uint256"
            },
            {
              "internalType": "uint256",
              "name": "itemIndex",
              "type": "uint256"
            }
          ],
          "internalType": "struct FulfillmentComponent[][]",
          "name": "considerationFulfillments",
          "type": "tuple[][]"
        },
        {
          "internalType": "uint256",
          "name": "maximumFulfilled",
          "type": "uint256"
        }
      ],
      "name": "fulfillAvailableOrders",
      "outputs": [],
      "stateMutability": "payable",
      "type": "function"
    },
    {
      "inputs": [
        {
          "components": [
            {
              "components": [
                {
                  "internalType": "address",
                  "name": "offerer",
                  "type": "address"
                },
                {
                  "internalType": "address",
                  "name": "zone",
                  "type": "address"
                },
                {
                  "components": [
                    {
                      "internalType": "enum ItemType",
                      "name": "itemType",
                      "type": "uint8"
                    },
                    {
                      "internalType": "address",
                      "name": "token",
                      "type": "address"
                    },
                    {
                      "internalType": "uint256",
                      "name": "identifierOrCriteria",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "startAmount",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "endAmount",
                      "type": "uint256"
                    }
                  ],
                  "internalType": "struct OfferItem[]",
                  "name": "offer",
                  "type": "tuple[]"
                },
                {
                  "components": [
                    {
                      "internalType": "enum ItemType",
                      "name": "itemType",
                      "type": "uint8"
                    },
                    {
                      "internalType": "address",
                      "name": "token",
                      "type": "address"
                    },
                    {
                      "internalType": "uint256",
                      "name": "identifierOrCriteria",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "startAmount",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "endAmount",
                      "type": "uint256"
                    },
                    {
                      "internalType": "address payable",
                      "name": "recipient",
                      "type": "address"
                    }
                  ],
                  "internalType": "struct ConsiderationItem[]",
                  "name": "consideration",
                  "type": "tuple[]"
                },
                {
                  "internalType": "enum OrderType",
                  "name": "orderType",
                  "type": "uint8"
                },
                {
                  "internalType": "uint256",
                  "name": "startTime",
                  "type": "uint256"
                },
                {
                  "internalType": "uint256",
                  "name": "endTime",
                  "type": "uint256"
                },
                {
                  "internalType": "bytes32",
                  "name": "zoneHash",
                  "type": "bytes32"
                },
                {
                  "internalType": "uint256",
                  "name": "salt",
                  "type": "uint256"
                },
                {
                  "internalType": "bytes32",
                  "name": "conduitKey",
                  "type": "bytes32"
                },
                {
                  "internalType": "uint256",
                  "name": "totalOriginalConsiderationItems",
                  "type": "uint256"
                }
              ],
              "internalType": "struct OrderParameters",
              "name": "parameters",
              "type": "tuple"
            },
            {
              "internalType": "bytes",
              "name": "signature",
              "type": "bytes"
            }
          ],
          "internalType": "struct Order",
          "name": "order",
          "type": "tuple"
        }
      ],
      "name": "fulfillOrder",
      "outputs": [],
      "stateMutability": "payable",
      "type": "function"
    },
    {
      "inputs": [
        {
          "components": [
            {
              "components": [
                {
                  "internalType": "address",
                  "name": "offerer",
                  "type": "address"
                },
                {
                  "internalType": "address",
                  "name": "zone",
                  "type": "address"
                },
                {
                  "components": [
                    {
                      "internalType": "enum ItemType",
                      "name": "itemType",
                      "type": "uint8"
                    },
                    {
                      "internalType": "address",
                      "name": "token",
                      "type": "address"
                    },
                    {
                      "internalType": "uint256",
                      "name": "identifierOrCriteria",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "startAmount",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "endAmount",
                      "type": "uint256"
                    }
                  ],
                  "internalType": "struct OfferItem[]",
                  "name": "offer",
                  "type": "tuple[]"
                },
                {
                  "components": [
                    {
                      "internalType": "enum ItemType",
                      "name": "itemType",
                      "type": "uint8"
                    },
                    {
                      "internalType": "address",
                      "name": "token",
                      "type": "address"
                    },
                    {
                      "internalType": "uint256",
                      "name": "identifierOrCriteria",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "startAmount",
                      "type": "uint256"
                    },
                    {
                      "internalType": "uint256",
                      "name": "endAmount",
                      "type": "uint256"
                    },
                    {
                      "internalType": "address payable",
                      "name": "recipient",
                      "type": "address"
                    }
                  ],
                  "internalType": "struct ConsiderationItem[]",
                  "name": "consideration",
                  "type": "tuple[]"
                },
                {
                  "internalType": "enum OrderType",
                  "name": "orderType",
                  "type": "uint8"
                },
                {
                  "internalType": "uint256",
                  "name": "startTime",
                  "type": "uint256"
                },
                {
                  "internalType": "uint256",
                  "name": "endTime",
                  "type": "uint256"
                },
                {
                  "internalType": "bytes32",
                  "name": "zoneHash",
                  "type": "bytes32"
                },
                {
                  "internalType": "uint256",
                  "name": "salt",
                  "type": "uint256"
                },
                {
                  "internalType": "bytes32",
                  "name": "conduitKey",
                  "type": "bytes32"
                },
                {
                  "internalType": "uint256",
                  "name": "totalOriginalConsiderationItems",
                  "type": "uint256"
                }
              ],
              "internalType": "struct OrderParameters",
              "name": "parameters",
              "type": "tuple"
            },
            {
              "internalType": "bytes",
              "name": "signature",
              "type": "bytes"
            }
          ],
          "internalType": "struct Order",
          "name": "_order",
          "type": "tuple"
        },
        {
          "internalType": "address",
          "name": "_recipient",
          "type": "address"
        }
      ],
      "name": "getRewardInOP",
      "outputs": [
        {
          "internalType": "uint256",
          "name": "",
          "type": "uint256"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "string",
          "name": "_campaignId",
          "type": "string"
        }
      ],
      "name": "getRewardSentByCampaignInOP",
      "outputs": [
        {
          "internalType": "uint256",
          "name": "",
          "type": "uint256"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "contract Seaport",
          "name": "_seaport",
          "type": "address"
        },
        {
          "internalType": "contract IRewardDeriver",
          "name": "_rewardDeriver",
          "type": "address"
        },
        {
          "internalType": "address",
          "name": "_marketplaceOwner",
          "type": "address"
        }
      ],
      "name": "initialize",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "address",
          "name": "newOwner",
          "type": "address"
        }
      ],
      "name": "initiateOwnershipTransfer",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "address",
          "name": "",
          "type": "address"
        },
        {
          "internalType": "address",
          "name": "",
          "type": "address"
        },
        {
          "internalType": "uint256[]",
          "name": "",
          "type": "uint256[]"
        },
        {
          "internalType": "uint256[]",
          "name": "",
          "type": "uint256[]"
        },
        {
          "internalType": "bytes",
          "name": "",
          "type": "bytes"
        }
      ],
      "name": "onERC1155BatchReceived",
      "outputs": [
        {
          "internalType": "bytes4",
          "name": "",
          "type": "bytes4"
        }
      ],
      "stateMutability": "pure",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "address",
          "name": "",
          "type": "address"
        },
        {
          "internalType": "address",
          "name": "",
          "type": "address"
        },
        {
          "internalType": "uint256",
          "name": "",
          "type": "uint256"
        },
        {
          "internalType": "uint256",
          "name": "",
          "type": "uint256"
        },
        {
          "internalType": "bytes",
          "name": "",
          "type": "bytes"
        }
      ],
      "name": "onERC1155Received",
      "outputs": [
        {
          "internalType": "bytes4",
          "name": "",
          "type": "bytes4"
        }
      ],
      "stateMutability": "pure",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "owner",
      "outputs": [
        {
          "internalType": "address",
          "name": "",
          "type": "address"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "pause",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "paused",
      "outputs": [
        {
          "internalType": "bool",
          "name": "",
          "type": "bool"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "potentialOwner",
      "outputs": [
        {
          "internalType": "address",
          "name": "",
          "type": "address"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "renounceOwnership",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "rewardDeriver",
      "outputs": [
        {
          "internalType": "contract IRewardDeriver",
          "name": "",
          "type": "address"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "seaport",
      "outputs": [
        {
          "internalType": "contract Seaport",
          "name": "",
          "type": "address"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "contract IRewardDeriver",
          "name": "_rewardDeriver",
          "type": "address"
        }
      ],
      "name": "setRewardDeriver",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "bytes4",
          "name": "interfaceId",
          "type": "bytes4"
        }
      ],
      "name": "supportsInterface",
      "outputs": [
        {
          "internalType": "bool",
          "name": "",
          "type": "bool"
        }
      ],
      "stateMutability": "pure",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "unpause",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "withdrawETH",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "stateMutability": "payable",
      "type": "receive"
    }
  ]
""")