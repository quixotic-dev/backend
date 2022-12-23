import os
import re
from itertools import repeat

from eth_account import Account
from jsonschema import validate

from .smart_contract_json_schema import launchpad_smart_contract_schema

BOUNCER_PRIVATE_KEY = os.environ.get(
    "BOUNCER_PRIVATE_KEY",
    "0x0000000000000000000000000000000000000000000000000000000000000000",
)
BOUNCER_ADDRESS = Account.from_key(BOUNCER_PRIVATE_KEY).address


def validate_launchpad_init(init):
    validate(instance=init, schema=launchpad_smart_contract_schema)


def create_public_mint(public_mint_dict):
    max_mint_per_addr = public_mint_dict.get("maxMintPerAddr")
    price = public_mint_dict.get("priceInWei")
    address_num_minted_mapping_decl = (
        "mapping(address => uint256) addressToNumberMinted;"
    )
    sale_is_active_declaration = "bool public saleIsActive = false;"
    flip_sale_state_func = """
    function flipSaleState() public onlyOwner {
            saleIsActive = !saleIsActive;
    }
"""
    mint_token_func = f"""
    function mintToken(uint numberOfTokens) public payable nonReentrant {{
        require(tx.origin == _msgSender(), "This function is only callable from an EOA.");
        require(saleIsActive, "Sale must be active to mint Tokens");
        require(numberOfTokens + addressToNumberMinted[_msgSender()] <= {max_mint_per_addr}, "Exceeded max token purchase");

        require(totalSupply() + numberOfTokens <= MAX_TOKENS, "Purchase would exceed max supply of tokens");
        require({price} * numberOfTokens <= msg.value, "Ether value sent is not correct");

        for (uint i = 0; i < numberOfTokens; i++) {{
            uint mintIndex = totalSupply();
            if (totalSupply() < MAX_TOKENS) {{
                addressToNumberMinted[_msgSender()] += 1;
                _safeMint(_msgSender(), mintIndex);
            }}
        }}
    }}
"""
    return (
        address_num_minted_mapping_decl,
        sale_is_active_declaration,
        flip_sale_state_func,
        mint_token_func,
    )


def create_green_list(greenlist_dict):
    active_decl = "bool public greenListSaleIsActive = false;"

    bouncer_decl = f"address private bouncer = {BOUNCER_ADDRESS};"

    max_mint_per_address = greenlist_dict.get("maxMintPerAddress")
    price = greenlist_dict.get("priceInWei")

    address_greenlist_mapping_decl = (
        "mapping(address => uint256) addressToGreenListNumberMinted;"
    )

    flip_sale_state_func = """
    function flipGreenListSaleState() public onlyOwner {
            greenListSaleIsActive = !greenListSaleIsActive;
    }
"""

    green_list_mint_func = f"""
    function greenListMintToken(uint numberOfTokens, bytes memory signature) public payable nonReentrant {{
        require(tx.origin == _msgSender(), "This function is only callable from an EOA.");
        require(greenListSaleIsActive, "Sale must be active to mint Tokens");
        require(numberOfTokens + addressToGreenListNumberMinted[_msgSender()] <= {max_mint_per_address}, "Exceeded max token purchase");
        require(totalSupply() + numberOfTokens <= MAX_TOKENS, "Purchase would exceed max supply of tokens");
        require({price} * numberOfTokens <= msg.value, "Ether value sent is not correct");

        bytes32 hashedMinter = ECDSA.toEthSignedMessageHash(keccak256(abi.encodePacked(_msgSender())));
        address recoveredBouncer = ECDSA.recover(hashedMinter, signature);
        require(recoveredBouncer == bouncer, "The signature for the greenlist is invalid");

        for (uint i = 0; i < numberOfTokens; i++) {{
            uint mintIndex = totalSupply();
            if (totalSupply() < MAX_TOKENS) {{
                addressToGreenListNumberMinted[_msgSender()] += 1;
                _safeMint(_msgSender(), mintIndex);
            }}
        }}
    }}
    """
    return (
        active_decl,
        address_greenlist_mapping_decl,
        bouncer_decl,
        flip_sale_state_func,
        green_list_mint_func,
    )


def create_reserve_tokens():
    reserve_token_func = f"""
    function reserveTokens(uint quantity, address recipient) public onlyOwner {{
        uint supply = totalSupply();
        require(supply + quantity <= MAX_TOKENS, "We have already hit the reserve limit");
        uint i;
        for (i = 0; i < quantity; i++) {{
            uint mintIndex = totalSupply();
            _safeMint(recipient, mintIndex);
        }}
    }}
"""

    return reserve_token_func


def write_smart_contract_src_code(init):
    validate_launchpad_init(init)
    name = re.sub(r"[^a-zA-Z0-9 ]+", "", init["name"])
    symbol = re.sub(r"[^a-zA-Z0-9]+", "", init["symbol"])
    max_tokens = init["maxTokens"]
    public_mint = init.get("publicMint")
    reserve_tokens = init.get("reserveTokens")
    green_list = init.get("greenList")

    if public_mint:
        (
            address_num_minted_mapping_decl,
            sale_is_active_declaration,
            flip_sale_state_func,
            mint_token_func,
        ) = create_public_mint(public_mint)
    else:
        (
            address_num_minted_mapping_decl,
            sale_is_active_declaration,
            flip_sale_state_func,
            mint_token_func,
            *_,
        ) = repeat("", 10)

    if reserve_tokens:
        reserve_token_func = create_reserve_tokens()
    else:
        reserve_token_func = ""

    if green_list:
        (
            gl_active_decl,
            address_greenlist_mapping_decl,
            bouncer_decl,
            gl_flip_sale_state_func,
            green_list_mint_func,
        ) = create_green_list(green_list)

    else:
        (
            gl_active_decl,
            address_greenlist_mapping_decl,
            bouncer_decl,
            gl_flip_sale_state_func,
            green_list_mint_func,
            *_,
        ) = repeat("", 10)
    launchpad_src = f"""
// File Contracts/LaunchpadNFT.sol

pragma solidity ^0.8.1;



contract QuixoticLaunchpadERC721 is ERC721("{name}", "{symbol}"), ERC721Enumerable, Ownable, ReentrancyGuard {{

    string private _baseURIextended;
    string private _baseURISuffix = "";
    bool public frozenMetadata = false;
    uint256 public MAX_TOKENS = {max_tokens};
    {sale_is_active_declaration}
    {gl_active_decl}
    {address_greenlist_mapping_decl}
    {address_num_minted_mapping_decl}
    {bouncer_decl}

    bool private _baseUriIncludeTokenId = true;

    function _beforeTokenTransfer(address from, address to, uint256 tokenId) internal override(ERC721, ERC721Enumerable) {{
        super._beforeTokenTransfer(from, to, tokenId);
    }}

    function supportsInterface(bytes4 interfaceId) public view virtual override(ERC721, ERC721Enumerable) returns (bool) {{
        return super.supportsInterface(interfaceId);
    }}

    {flip_sale_state_func}

    {gl_flip_sale_state_func}

    function setBaseURI(string memory baseURI_, bool includeTokenId, string memory suffix) external onlyOwner() {{
        require(!frozenMetadata, "The metadata URI is frozen. You can no longer set the baseURI");
        _baseUriIncludeTokenId = includeTokenId;
        _baseURIextended = baseURI_;
        _baseURISuffix = suffix;
    }}

    function _baseURI() internal view virtual override returns (string memory) {{
        return _baseURIextended;
    }}

    function freezeMetadata() external onlyOwner {{
        frozenMetadata = true;
    }}

    function tokenURI(uint256 tokenId) public view virtual override returns (string memory) {{
        require(_exists(tokenId), "ERC721Metadata: URI query for nonexistent token");

        string memory baseURI = _baseURI();
        if (_baseUriIncludeTokenId) {{
            return bytes(baseURI).length > 0 ? string(abi.encodePacked(baseURI, Strings.toString(tokenId), _baseURISuffix)) : "";        
        }} else {{
            return bytes(baseURI).length > 0 ? string(abi.encodePacked(baseURI)) : "";
        }}
    }}

    {mint_token_func}

    {green_list_mint_func}

    {reserve_token_func}

}}
"""
    return launchpad_src
