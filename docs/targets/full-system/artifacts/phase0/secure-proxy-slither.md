# Slither Findings — secure-proxy

**THIS CHECKLIST IS NOT COMPLETE**. Use `--show-ignored-findings` to show all the results.
Summary
 - [uninitialized-local](#uninitialized-local) (1 results) (Medium)
 - [missing-zero-check](#missing-zero-check) (1 results) (Low)
 - [timestamp](#timestamp) (4 results) (Low)
 - [assembly](#assembly) (3 results) (Informational)
 - [pragma](#pragma) (1 results) (Informational)
 - [dead-code](#dead-code) (1 results) (Informational)
 - [low-level-calls](#low-level-calls) (1 results) (Informational)
 - [naming-convention](#naming-convention) (2 results) (Informational)
 - [unimplemented-functions](#unimplemented-functions) (1 results) (Informational)
## uninitialized-local
Impact: Medium
Confidence: Medium
 - [ ] ID-0
[SecureProxy.securePause(uint256,string).pausedUntil](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L288) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L288


## missing-zero-check
Impact: Low
Confidence: Medium
 - [ ] ID-1
[SecureProxy.constructor(address,address,bytes32,bytes).initialImplementation_](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L69) lacks a zero-check on :
		- [(success,None) = initialImplementation_.delegatecall(initializationData_)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L88)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L69


## timestamp
Impact: Low
Confidence: Medium
 - [ ] ID-2
[SecureProxy.securePauseState()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L338-L349) uses timestamp for comparisons
	Dangerous comparisons:
	- [paused = pauseExpiration >= block.timestamp](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L348)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L338-L349


 - [ ] ID-3
[SecureProxy.securePause(uint256,string)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L254-L301) uses timestamp for comparisons
	Dangerous comparisons:
	- [ptrCodeStorage.expires <= block.timestamp](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L268)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L254-L301


 - [ ] ID-4
[SecureProxy.secureCheckPauseCode(uint256,bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L316-L328) uses timestamp for comparisons
	Dangerous comparisons:
	- [ptrCodeStorage.expires <= block.timestamp](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L323)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L316-L328


 - [ ] ID-5
[SecureProxy._checkPauseState(bool)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L425-L445) uses timestamp for comparisons
	Dangerous comparisons:
	- [pauseExpiration < block.timestamp](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L429)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L425-L445


## assembly
Impact: Informational
Confidence: High
 - [ ] ID-6
[SecureProxy._fallback()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L450-L464) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L453-L463)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L450-L464


 - [ ] ID-7
[SecureProxy._setImplementation(address)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L401-L411) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L406-L408)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L401-L411


 - [ ] ID-8
[SecureProxy._securityStorage()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L469-L473) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L470-L472)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L469-L473


## pragma
Impact: Informational
Confidence: High
 - [ ] ID-9
2 different versions of Solidity are used:
	- Version constraint ^0.8.4 is used by:
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/lib/tm-core-lib/src/utils/Context.sol#L2)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/lib/tm-core-lib/src/utils/Errors.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/lib/tm-core-lib/src/utils/security/IRoleClient.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/lib/tm-core-lib/src/utils/security/IRoleServer.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/lib/tm-core-lib/src/utils/security/RoleClientBase.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/lib/tm-core-lib/src/utils/security/RoleSetClient.sol#L1)
	- Version constraint 0.8.24 is used by:
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/Constants.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/Errors.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L2)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/lib/tm-core-lib/src/utils/Context.sol#L2


## dead-code
Impact: Informational
Confidence: Medium
 - [ ] ID-10
[SecureProxy._setupRoles(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L487-L490) is never used and should be removed

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L487-L490


## low-level-calls
Impact: Informational
Confidence: High
 - [ ] ID-11
Low level call in [SecureProxy.constructor(address,address,bytes32,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L68-L93):
	- [(success,None) = initialImplementation_.delegatecall(initializationData_)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L88)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L68-L93


## naming-convention
Impact: Informational
Confidence: High
 - [ ] ID-12
Variable [SecureProxy.SECURE_PROXY_CODE_MANAGER_ROLE](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L48) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L48


 - [ ] ID-13
Variable [SecureProxy.SECURE_PROXY_ADMIN_ROLE](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L51) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L51


## unimplemented-functions
Impact: Informational
Confidence: High
 - [ ] ID-14
[SecureProxy](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L46-L491) does not implement functions:
	- [RoleSetClient._setupRoles(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/lib/tm-core-lib/src/utils/security/RoleSetClient.sol#L18)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/secure-proxy/src/SecureProxy.sol#L46-L491


