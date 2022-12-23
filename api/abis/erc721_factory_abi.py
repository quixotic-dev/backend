erc721_factory_abi = [
    {
        "inputs": [
            {"internalType": "address", "name": "_bridge", "type": "address"},
            {"internalType": "uint256", "name": "_remoteChainId", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "constructor",
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "localToken",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "remoteToken",
                "type": "address",
            },
            {
                "indexed": False,
                "internalType": "address",
                "name": "deployer",
                "type": "address",
            },
        ],
        "name": "OptimismMintableERC721Created",
        "type": "event",
    },
    {
        "inputs": [],
        "name": "bridge",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "_remoteToken", "type": "address"},
            {"internalType": "string", "name": "_name", "type": "string"},
            {"internalType": "string", "name": "_symbol", "type": "string"},
        ],
        "name": "createOptimismMintableERC721",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "", "type": "address"}],
        "name": "isOptimismMintableERC721",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "remoteChainId",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "version",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
]
