# Candlestick Patterns Guide

This guide explains common candlestick types and what they usually represent.

## 1) Candlestick Anatomy

Each candle is built from four prices:

- Open: price at period start
- High: highest price in period
- Low: lowest price in period
- Close: price at period end

Basic structure:

```text
        High
         |
     +-------+
     | Body  |   <- Open and Close make the body
     +-------+
         |
         Low
```

Interpretation:

- Bullish candle: Close > Open (buyers won the period)
- Bearish candle: Close < Open (sellers won the period)
- Body size: strength of move
- Wicks/shadows: rejection of higher/lower prices

---

## 2) Single-Candle Types

### 2.1 Bullish Candle

```text
   H
   |
 [ C ]
 [   ]
 [ O ]
   |
   L
```

Represents: Buyers pushed price up from open to close.

### 2.2 Bearish Candle

```text
   H
   |
 [ O ]
 [   ]
 [ C ]
   |
   L
```

Represents: Sellers pushed price down from open to close.

### 2.3 Doji

```text
   H
   |
  ---   <- Open almost equal to Close
   |
   L
```

Represents: Indecision or balance between buyers and sellers.

### 2.4 Hammer

```text
   H
   |
 [ O/C ]
    |
    |
    |
    L
```

Represents: Strong rejection of lower prices. Often bullish after a decline.

### 2.5 Shooting Star

```text
    H
    |
    |
    |
 [ O/C ]
    |
    L
```

Represents: Strong rejection of higher prices. Often bearish after a rise.

### 2.6 Marubozu (Strong Trend Candle)

```text
Bullish Marubozu:            Bearish Marubozu:
    H                             H
 [ C ]                         [ O ]
 [   ]                         [   ]
 [ O ]                         [ C ]
    L                             L
```

Represents: Very strong directional conviction (little to no wick).

### 2.7 Spinning Top

```text
   H
   |
 [O/C]
 [ C/O]
   |
   L
```

Represents: Small body with wicks on both sides; uncertainty, possible pause.

---

## 3) Multi-Candle Patterns

### 3.1 Bullish Engulfing

```text
Day 1: small bearish body
Day 2: larger bullish body that fully covers Day 1 body
```

Represents: Potential bullish reversal after weakness.

### 3.2 Bearish Engulfing

```text
Day 1: small bullish body
Day 2: larger bearish body that fully covers Day 1 body
```

Represents: Potential bearish reversal after strength.

### 3.3 Morning Star (3 candles)

```text
1) Bearish candle
2) Small indecision candle
3) Strong bullish candle
```

Represents: Potential bullish reversal from a down move.

### 3.4 Evening Star (3 candles)

```text
1) Bullish candle
2) Small indecision candle
3) Strong bearish candle
```

Represents: Potential bearish reversal from an up move.

### 3.5 Harami (Inside Body Pattern)

```text
Large body candle
Then smaller opposite/neutral body inside prior body
```

Represents: Momentum slowdown and possible reversal.

---

## 4) Patterns Used in This Project

Your current signal flow uses these candlestick patterns:

- bullish_engulfing
- bearish_engulfing
- hammer
- shooting_star
- doji
- morning_star
- evening_star

These are detected and then combined with indicators (RSI, SMA, MACD, volume trend) for final signal scoring.

---

## 5) Practical Use Notes

- Candlestick patterns are not guarantees.
- Use confirmation from trend, volume, and indicators.
- Reliability improves when pattern aligns with support/resistance and broader market context.
- In downtrend markets, bullish patterns can fail more often without follow-through.

---

## 6) Quick Reference

- Hammer + support + rising volume: bullish candidate
- Shooting star after rally + weak breadth: bearish warning
- Doji near key level: wait for next candle confirmation
- Engulfing with momentum confirmation: stronger setup than engulfing alone

