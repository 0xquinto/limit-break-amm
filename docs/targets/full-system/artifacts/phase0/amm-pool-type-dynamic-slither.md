# Slither Findings — amm-pool-type-dynamic

**THIS CHECKLIST IS NOT COMPLETE**. Use `--show-ignored-findings` to show all the results.
Summary
 - [incorrect-shift](#incorrect-shift) (2 results) (High)
 - [divide-before-multiply](#divide-before-multiply) (21 results) (Medium)
 - [uninitialized-local](#uninitialized-local) (4 results) (Medium)
 - [assembly](#assembly) (9 results) (Informational)
 - [pragma](#pragma) (1 results) (Informational)
 - [cyclomatic-complexity](#cyclomatic-complexity) (3 results) (Informational)
 - [naming-convention](#naming-convention) (1 results) (Informational)
 - [too-many-digits](#too-many-digits) (1 results) (Informational)
## incorrect-shift
Impact: High
Confidence: High
 - [ ] ID-0
[BitMath.leastSignificantBit(uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L33-L50) contains an incorrect shift operation: [r = 0x8040405543005266443200005020610674053026020000107506200176117077 << x * 0xb6db6db6ddddddddd34d34d349249249210842108c6318c639ce739cffffffff >> 250 << 2 >> 252 << 5](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L42-L44)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L33-L50


 - [ ] ID-1
[BitMath.mostSignificantBit(uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L14-L27) contains an incorrect shift operation: [r = r | byte(uint256,uint256)(0x1f & 0x8421084210842108cc6318c6db6d54be >> x >> r,0x0706060506020500060203020504000106050205030304010505030400000000)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L24-L25)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L14-L27


## divide-before-multiply
Impact: Medium
Confidence: Medium
 - [ ] ID-2
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0x31be135f97d08fd981231505542fcfa6) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L83)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-3
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xfff97272373d413259a46990580e213a) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L69)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-4
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xd097f3bdfd2022b8845ad8f792aa5825) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L80)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-5
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0x48a170391f7dc42444e8fa2) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L87)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-6
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xf987a7253ac413176f2b074cf7815e54) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L77)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-7
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xfcbe86c7900a88aedcffc83b479aa3a4) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L76)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-8
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xa9f746462d870fdf8a65dc1f90e061e5) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L81)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-9
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xff973b41fa98c081472e6896dfb254c0) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L73)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-10
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0x9aa508b5b7a84e1c677de54f3e99bc9) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L84)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-11
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xff2ea16466c96a3843ec78b326b52861) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L74)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-12
[DynamicHelper._poolMaxLiquidityPerTick(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L641-L650) performs a multiplication on the result of a division:
	- [minTick = (MIN_TICK / tickSpacing) * tickSpacing](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L644)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L641-L650


 - [ ] ID-13
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xe7159475a2c29b7443b29c7fa6e889d9) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L79)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-14
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0x2216e584f5fa1ea926041bedfe98) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L86)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-15
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xffe5caca7e10e4e61c3624eaa0941cd0) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L71)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-16
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xffcb9843d60f6159c9db58835c926644) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L72)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-17
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0x70d869a156d2a1b890bb3df62baf32f7) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L82)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-18
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xf3392b0822b70005940c7a398e4b70f3) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L78)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-19
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xfe5dee046a99a2a811c461f1969c3053) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L75)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-20
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0x5d6af8dedb81196699c329225ee604) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L85)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-21
[DynamicHelper._poolMaxLiquidityPerTick(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L641-L650) performs a multiplication on the result of a division:
	- [maxTick = (MAX_TICK / tickSpacing) * tickSpacing](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L645)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L641-L650


 - [ ] ID-22
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) performs a multiplication on the result of a division:
	- [price = (price * 0xfff2e50f5f656932ef12357cf3c7fdcc) >> 128](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L70)
	- [price = ~ 0 / price](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L91)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


## uninitialized-local
Impact: Medium
Confidence: Medium
 - [ ] ID-23
[DynamicPoolType.addLiquidity(bytes32,address,bytes32,bytes).liquidityCache](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/DynamicPoolType.sol#L244) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/DynamicPoolType.sol#L244


 - [ ] ID-24
[DynamicPoolType.removeLiquidity(bytes32,address,bytes32,bytes).liquidityCache](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/DynamicPoolType.sol#L333) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/DynamicPoolType.sol#L333


 - [ ] ID-25
[DynamicPoolType.collectFees(bytes32,address,bytes32,bytes).liquidityCache](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/DynamicPoolType.sol#L173) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/DynamicPoolType.sol#L173


 - [ ] ID-26
[SqrtPriceMath.computeRatioX96(uint256,uint256).multiplier](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L253) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L253


## assembly
Impact: Informational
Confidence: High
 - [ ] ID-27
[BitMath.mostSignificantBit(uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L14-L27) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L17-L26)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L14-L27


 - [ ] ID-28
[SqrtPriceMath.getAmount1Delta(uint160,uint160,uint128,bool)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L164-L178) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L175-L177)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L164-L178


 - [ ] ID-29
[TickMath.getTickAtSqrtPrice(uint160)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L120-L236) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L140-L145)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L146-L151)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L152-L157)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L158-L163)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L164-L169)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L170-L175)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L176-L181)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L182-L187)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L188-L193)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L194-L199)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L200-L205)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L206-L211)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L212-L217)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L218-L222)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L120-L236


 - [ ] ID-30
[SqrtPriceMath.absDiff(uint160,uint160)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L138-L149) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L139-L148)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L138-L149


 - [ ] ID-31
[BitMath.leastSignificantBit(uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L33-L50) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L36-L49)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L33-L50


 - [ ] ID-32
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L45-L53)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L66-L68)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L89-L99)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


 - [ ] ID-33
[SqrtPriceMath._sqrt(uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L281-L332) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L283-L331)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L281-L332


 - [ ] ID-34
[LiquidityMath.addDelta(uint128,int128)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/LiquidityMath.sol#L34-L43) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/LiquidityMath.sol#L35-L42)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/LiquidityMath.sol#L34-L43


 - [ ] ID-35
[SqrtPriceMath._getNextSqrtPriceFromAmount0RoundingUp(uint160,uint128,uint256,bool)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L353-L397) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L382-L392)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L353-L397


## pragma
Impact: Informational
Confidence: High
 - [ ] ID-36
5 different versions of Solidity are used:
	- Version constraint ^0.8.4 is used by:
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/../lbamm-core/lib/tm-core-lib/src/utils/Errors.sol#L1)
	- Version constraint 0.8.24 is used by:
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/../lbamm-core/src/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/../lbamm-core/lib/tm-core-lib/src/utils/math/FullMath.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/../lbamm-core/lib/tm-core-lib/src/utils/misc/SafeCast.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/../lbamm-core/src/interfaces/ILimitBreakAMMPoolType.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/DynamicPoolType.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/Errors.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/interfaces/IDynamicPoolType.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicPoolDecoder.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/LiquidityMath.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/SwapMath.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L2)
	- Version constraint ^0.8.13 is used by:
		-[^0.8.13](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/../lbamm-core/lib/tm-core-lib/src/utils/cryptography/EfficientHash.sol#L2)
	- Version constraint ^0.8.0 is used by:
		-[^0.8.0](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/../lbamm-core/lib/tm-core-lib/src/utils/math/UnsafeMath.sol#L2)
	- Version constraint ^0.8.24 is used by:
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/../lbamm-core/lib/tm-core-lib/src/utils/misc/StaticDelegateCall.sol#L2)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/Constants.sol#L2)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/../lbamm-core/lib/tm-core-lib/src/utils/Errors.sol#L1


## cyclomatic-complexity
Impact: Informational
Confidence: High
 - [ ] ID-37
[DynamicHelper.snapPrice(DynamicPoolStorage,bytes32,uint160)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L237-L291) has a high cyclomatic complexity (12).

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L237-L291


 - [ ] ID-38
[DynamicHelper.computeSwap(DynamicPoolStorage,DynamicSwapCache,DynamicPoolState,uint16,function(DynamicSwapCache,StepComputations,uint16))](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L350-L433) has a high cyclomatic complexity (17).

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L350-L433


 - [ ] ID-39
[TickMath.getSqrtPriceAtTick(int24)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101) has a high cyclomatic complexity (22).

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/TickMath.sol#L42-L101


## naming-convention
Impact: Informational
Confidence: High
 - [ ] ID-40
Parameter [DynamicHelper.computeSwap(DynamicPoolStorage,DynamicSwapCache,DynamicPoolState,uint16,function(DynamicSwapCache,StepComputations,uint16))._swapStep](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L355) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/DynamicHelper.sol#L355


## too-many-digits
Impact: Informational
Confidence: Medium
 - [ ] ID-41
[BitMath.mostSignificantBit(uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L14-L27) uses literals with too many digits:
	- [r = r | byte(uint256,uint256)(0x1f & 0x8421084210842108cc6318c6db6d54be >> x >> r,0x0706060506020500060203020504000106050205030304010505030400000000)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L24-L25)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/amm-pool-type-dynamic/src/libraries/BitMath.sol#L14-L27


