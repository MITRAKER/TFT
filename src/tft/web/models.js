/**
 * The 3D characters: every champion is a little figure built from solid shapes, and so are the
 * things that stand around the arena.
 *
 * A figure stands on the ground at y = 0, faces +z and is about two units tall. A part is the
 * string "<kind> x y z | sx sy sz | #colour [| rx ry rz]": where its centre is, its half-sizes,
 * its colour and, when it is turned, its rotation in degrees about x, y and z.
 *
 *   s  ball (an ellipsoid)      c  cylinder, along y       k  cone, tip up
 *   b  box                      t  ring, lying flat (its y size is the thickness of the tube)
 *   e  eye, looking along z: a white ball, the iris in the part's colour, a pupil and a point
 *      of light; in the frame where a figure blinks it is a dark lid instead
 *
 * A capital letter makes the part and its mirror image across x = 0: ears, eyes, arms, legs.
 * A colour followed by "!" shines by itself: it is not shaded.
 *
 * A kind followed by ":" and a motion is a limb that moves by itself (studio.js says how far):
 *
 *   :arm :leg   swing forward and back from their top end, against each other
 *   :ear        flops sideways from its bottom end         :wing  flaps from its inner end
 *   :wag        wags from side to side about its bottom end
 *   :bob        floats up and down                         :tip   one side up, the other down
 *
 * A kind followed by "+" moves with the limb before it on its side: a hand with its arm.
 */
import { turnMatrix } from "./studio.js";

export const KINDS = { s: "ball", c: "cylinder", k: "cone", b: "box", t: "ring", e: "eye" };

const SKIN = "#f2d5b0";
const INK = "#141824";
const WHITE = "#f6f3ea";
const GOLD = "#ffc94d";
const PINK = "#f4a6b8";
const BLUSH = "#ff9db0";
const BRONZE = "#c98a3d";
const BRONZE_DARK = "#8f5a22";
const STEEL = "#93a7cc";
const STEEL_DARK = "#5f7096";
const STONE = "#2c3656";
const STONE_LIGHT = "#3d4a74";

export const MODELS = {
  "Pip Squeak": [
    "s 0 .5 0 | .38 .44 .34 | #9aa3b5",
    "s 0 .46 .14 | .27 .32 .25 | #e9e4da",
    "s 0 1.2 .05 | .5 .44 .44 | #9aa3b5",
    "S:ear .42 1.66 0 | .27 .27 .08 | #9aa3b5",
    `S+ .42 1.66 .05 | .18 .18 .05 | ${PINK}`,
    "s 0 1.08 .4 | .18 .13 .16 | #e9e4da",
    "s 0 1.13 .55 | .06 .05 .05 | #f4739a",
    `E .2 1.3 .4 | .1 .125 .07 | ${INK}`,
    `S .36 1.12 .32 | .08 .05 .05 | ${BLUSH}`,
    `S:leg .19 .07 .12 | .14 .08 .2 | ${PINK}`,
    `c:wag .46 .3 -.25 | .04 .32 .04 | ${PINK} | 0 0 -50`,
    "t 0 .84 .02 | .32 .5 .3 | #2ec7c9",
  ],
  "Index Drone": [
    "s 0 1 0 | .5 .36 .5 | #dfe6f3",
    "s 0 1 .28 | .34 .24 .3 | #1b2540",
    "e 0 1.01 .52 | .2 .2 .1 | #2f6fe0",
    "S .5 1.15 .41 | .22 .04 .06 | #8e9bb6 | 0 -40 0",
    "S .5 1.15 -.41 | .22 .04 .06 | #8e9bb6 | 0 40 0",
    "S .68 1.3 .55 | .28 .02 .28 | #6fb1ff!",
    "S .68 1.3 -.55 | .28 .02 .28 | #6fb1ff!",
    "S .68 1.24 .55 | .06 .08 .06 | #1b2540",
    "S .68 1.24 -.55 | .06 .08 .06 | #1b2540",
    "S .28 .45 0 | .04 .04 .45 | #8e9bb6",
    "S .28 .6 .2 | .03 .16 .03 | #8e9bb6",
    "S .28 .6 -.2 | .03 .16 .03 | #8e9bb6",
    "s 0 1.38 -.1 | .07 .05 .07 | #ff6470!",
  ],
  "Hodl Hamster": [
    "s 0 .6 0 | .56 .6 .5 | #e8a657",
    "s 0 .54 .2 | .42 .46 .36 | #fbe9c8",
    "s 0 1.32 .06 | .52 .45 .46 | #e8a657",
    "S .31 1.18 .28 | .21 .18 .18 | #fbe9c8",
    "S:ear .33 1.72 0 | .15 .16 .07 | #e8a657",
    `S+ .33 1.72 .04 | .09 .1 .04 | ${PINK}`,
    `E .19 1.44 .44 | .09 .115 .06 | ${INK}`,
    "s 0 1.3 .53 | .055 .045 .04 | #f4739a",
    `S .4 1.26 .42 | .07 .045 .04 | ${BLUSH}`,
    "S .34 .8 .34 | .12 .1 .16 | #e8a657",
    "k 0 .9 .56 | .17 .12 .17 | #9fecff!",
    "k 0 .68 .56 | .17 .1 .17 | #4fc3f7 | 180 0 0",
    `S:leg .26 .07 .16 | .16 .08 .22 | ${PINK}`,
  ],
  "Barrel Bo": [
    "c 0 .95 0 | .52 .68 .52 | #b5733c",
    "c 0 1.33 0 | .55 .05 .55 | #5b4636",
    "c 0 .57 0 | .55 .05 .55 | #5b4636",
    "c 0 1.64 0 | .46 .02 .46 | #8a5a33",
    `E .2 1.06 .5 | .11 .13 .06 | ${INK}`,
    `b 0 .8 .52 | .13 .03 .03 | ${INK}`,
    `S .37 .88 .39 | .07 .04 .04 | ${BLUSH}`,
    "S:arm .64 .95 0 | .1 .26 .1 | #8a5a33 | 0 0 -18",
    `S+ .74 .68 0 | .12 .12 .12 | ${SKIN}`,
    "S:leg .22 .16 0 | .1 .18 .1 | #5b4636",
    "S+ .22 .05 .08 | .14 .06 .2 | #2a2f45",
    "c 0 .64 .53 | .05 .04 .05 | #d8b25a | 90 0 0",
  ],
  "Coupon Clerk": [
    "s 0 .62 0 | .46 .58 .42 | #2f6f5e",
    `s 0 .6 .19 | .3 .42 .28 | ${WHITE}`,
    "k 0 .76 .44 | .07 .18 .04 | #36c98f | 180 0 0",
    `s 0 1.4 .02 | .45 .41 .41 | ${SKIN}`,
    "c 0 1.62 .14 | .47 .03 .47 | #36c98f",
    "t 0 1.62 .02 | .43 .3 .43 | #1f8f68",
    `E .17 1.42 .38 | .085 .1 .05 | ${INK}`,
    "T .17 1.42 .44 | .12 .22 .12 | #1b2540 | 90 0 0",
    "b 0 1.2 .39 | .07 .02 .02 | #b0705a",
    "S:arm .5 .76 .1 | .1 .24 .1 | #2f6f5e | 0 0 -25",
    "b+ .62 .62 .34 | .2 .12 .02 | #ffe9a8 | 0 -20 10",
    "S:leg .2 .06 .1 | .15 .07 .2 | #1b2540",
  ],
  "Candle Reader": [
    "k 0 .6 0 | .52 .64 .48 | #6a48c7",
    `s 0 1.38 .02 | .4 .37 .37 | ${SKIN}`,
    `k 0 1.1 .24 | .22 .28 .14 | ${WHITE} | 180 0 0`,
    "k 0 2 0 | .36 .42 .36 | #6a48c7",
    "c 0 1.62 0 | .52 .03 .52 | #5a3bb0",
    `s 0 1.92 .3 | .06 .06 .03 | ${GOLD}!`,
    `E .15 1.43 .34 | .075 .09 .045 | ${INK}`,
    `S .15 1.56 .33 | .09 .025 .03 | ${WHITE} | 0 0 12`,
    "S:arm .5 .9 .12 | .09 .2 .09 | #6a48c7 | 0 0 -30",
    "c+ .68 1.1 .2 | .02 .62 .02 | #dfe6f3",
    "b+ .68 1.15 .2 | .09 .26 .09 | #35d49a!",
  ],
  "Gap Gazelle": [
    "s 0 .66 0 | .38 .48 .34 | #d9a066",
    "s 0 .6 .14 | .27 .36 .25 | #f6e6c8",
    "c 0 1.1 .04 | .14 .2 .14 | #d9a066",
    "s 0 1.46 .1 | .34 .33 .38 | #d9a066",
    "s 0 1.36 .42 | .17 .14 .16 | #f6e6c8",
    "s 0 1.4 .57 | .06 .05 .04 | #2a2f45",
    `E .2 1.56 .35 | .08 .105 .05 | ${INK}`,
    "S:wing .38 1.64 0 | .17 .08 .06 | #d9a066 | 0 0 -25",
    "K .14 2.04 -.04 | .06 .36 .06 | #3b2f2a | -10 0 -8",
    "S:leg .18 .18 0 | .08 .2 .08 | #d9a066",
    "S+ .18 .04 .02 | .1 .05 .12 | #3b2f2a",
    "t 0 1 .03 | .21 .3 .21 | #4a8cf7",
    "s 0 .58 -.34 | .08 .08 .08 | #f6e6c8",
  ],
  "Mean Reverend": [
    "k 0 .62 0 | .54 .66 .48 | #2f4f9e",
    `t 0 1.12 0 | .26 .4 .24 | ${WHITE}`,
    `s 0 1.44 0 | .41 .39 .39 | ${SKIN}`,
    `t:bob 0 2.06 0 | .3 .2 .3 | ${GOLD}!`,
    `S .15 1.46 .36 | .085 .022 .03 | ${INK} | 0 0 8`,
    `S .3 1.34 .3 | .07 .04 .04 | ${BLUSH}`,
    "b 0 1.28 .38 | .05 .015 .02 | #b0705a",
    "b 0 .86 .46 | .22 .15 .05 | #8a5a33",
    `b 0 .86 .5 | .19 .12 .03 | ${WHITE}`,
    "S .36 .92 .28 | .1 .1 .22 | #2f4f9e",
  ],
  "Spread Spider": [
    "s 0 .7 -.3 | .5 .44 .5 | #3a2f55",
    "s 0 .98 -.34 | .2 .12 .22 | #2ec7c9!",
    "s 0 .74 .32 | .4 .36 .36 | #4b3d6e",
    `E .17 .86 .6 | .13 .145 .08 | ${INK}`,
    `S .36 1 .46 | .05 .05 .04 | ${WHITE}!`,
    "S:wag .7 .42 .46 | .045 .44 .045 | #2a2140 | 20 0 -55",
    "S:wag .76 .42 .16 | .045 .44 .045 | #2a2140 | 6 0 -55",
    "S:wag .76 .42 -.16 | .045 .44 .045 | #2a2140 | -6 0 -55",
    "S:wag .7 .42 -.46 | .045 .44 .045 | #2a2140 | -20 0 -55",
    `K .08 .56 .64 | .04 .08 .04 | ${WHITE} | 180 0 0`,
  ],
  "Gold Bug": [
    "s 0 .62 -.05 | .58 .5 .62 | #e2a51f",
    "b 0 .9 -.1 | .02 .26 .5 | #8a5a14",
    "s 0 .62 .5 | .36 .32 .32 | #3b2f2a",
    `E .17 .74 .74 | .11 .12 .065 | ${INK}`,
    "K:ear .14 1.08 .62 | .03 .2 .03 | #3b2f2a | 25 0 -15",
    `S+ .2 1.26 .72 | .05 .05 .05 | ${GOLD}!`,
    "S:leg .6 .22 .25 | .05 .2 .05 | #3b2f2a | 0 0 -40",
    "S:leg .64 .22 -.05 | .05 .2 .05 | #3b2f2a | 0 0 -40",
    "S:leg .6 .22 -.35 | .05 .2 .05 | #3b2f2a | 0 0 -40",
    "S .25 .98 .1 | .08 .04 .1 | #ffe38f",
  ],
  "Stable Coin": [
    `c 0 1 0 | .72 .1 .72 | ${GOLD} | 90 0 0`,
    "t 0 1 0 | .7 .5 .7 | #e09a1b | 90 0 0",
    "c 0 1 .1 | .54 .03 .54 | #ffd972 | 90 0 0",
    `E .21 1.1 .14 | .1 .125 .05 | ${INK}`,
    "b 0 .84 .15 | .12 .03 .02 | #8a5a14",
    `S .4 .92 .13 | .08 .05 .02 | ${BLUSH}`,
    "K .3 1.78 0 | .1 .14 .06 | #e09a1b",
    "S:leg .26 .16 0 | .08 .18 .08 | #8a5a14",
    "S+ .26 .04 .05 | .13 .05 .18 | #2a2f45",
    "S:arm .8 .95 0 | .08 .2 .08 | #e09a1b | 0 0 -30",
  ],
  "Yield Yeti": [
    "s 0 .78 0 | .68 .76 .56 | #eef2f8",
    "s 0 1.52 .04 | .52 .46 .46 | #eef2f8",
    "s 0 1.46 .3 | .34 .3 .22 | #8fb8e8",
    `E .15 1.55 .47 | .085 .1 .05 | ${INK}`,
    "b 0 1.33 .5 | .12 .03 .02 | #1b2540",
    "S .07 1.3 .51 | .03 .04 .02 | #ffffff",
    "K .34 2 0 | .1 .2 .1 | #bfe3ff | 0 0 -20",
    "S:arm .78 .82 .05 | .2 .44 .2 | #eef2f8 | 0 0 -12",
    "S+ .86 .4 .1 | .2 .16 .2 | #8fb8e8",
    "S:leg .34 .08 .14 | .26 .1 .3 | #8fb8e8",
    "S .5 1.2 -.1 | .2 .2 .2 | #ffffff",
  ],
  "Breakout Bull": [
    "s 0 .74 -.02 | .62 .66 .5 | #a8442e",
    "s 0 .8 .2 | .44 .46 .34 | #c85a3c",
    "s 0 1.46 .12 | .46 .4 .42 | #a8442e",
    "s 0 1.32 .46 | .28 .2 .2 | #f0c7a4",
    "S .1 1.33 .65 | .04 .04 .03 | #5b2a1e",
    `t 0 1.22 .62 | .1 .3 .1 | ${GOLD} | 90 0 0`,
    `E .21 1.58 .44 | .085 .1 .05 | ${INK}`,
    "S .21 1.71 .46 | .11 .03 .04 | #5b2a1e | 0 0 22",
    `K .52 1.84 .05 | .1 .3 .1 | ${WHITE} | 0 0 -42`,
    "S:wing .5 1.54 0 | .14 .08 .06 | #a8442e",
    "S:arm .7 .86 .1 | .17 .34 .17 | #a8442e | 0 0 -14",
    "S+ .78 .48 .14 | .17 .15 .17 | #5b2a1e",
    "S:leg .28 .18 0 | .15 .2 .15 | #a8442e",
    "S+ .28 .05 .04 | .17 .07 .2 | #2a2f45",
    "t 0 .5 0 | .56 .25 .46 | #4a8cf7",
  ],
  "Bear Baron": [
    "b 0 .86 -.42 | .5 .56 .04 | #b3273a | 8 0 0",
    "s 0 .72 0 | .6 .68 .5 | #7a4e2d",
    "s 0 .66 .2 | .4 .46 .34 | #c9a27a",
    "s 0 1.44 .06 | .48 .42 .42 | #7a4e2d",
    "s 0 1.34 .42 | .21 .17 .16 | #c9a27a",
    "s 0 1.4 .57 | .07 .05 .04 | #1b1b22",
    `E .2 1.54 .41 | .08 .095 .05 | ${INK}`,
    "S:ear .36 1.82 0 | .15 .15 .08 | #7a4e2d",
    `c 0 1.9 .02 | .22 .07 .22 | ${GOLD}`,
    `K .14 2.03 .02 | .05 .08 .05 | ${GOLD}`,
    `k 0 2.05 .12 | .05 .09 .05 | ${GOLD}`,
    "s 0 1.91 .22 | .05 .05 .03 | #ff6470!",
    "S:arm .68 .84 .06 | .17 .36 .17 | #7a4e2d | 0 0 -14",
    "S:leg .28 .08 .12 | .2 .09 .26 | #5b3a20",
  ],
  "Vol Vampire": [
    "S:wing .8 1.1 -.2 | .44 .3 .04 | #6a48c7 | 0 -25 -25",
    "k 0 .62 0 | .46 .64 .4 | #2a2140",
    "K .3 1.3 -.12 | .16 .3 .08 | #b3273a | 0 0 -18",
    "s 0 1.44 .04 | .42 .39 .39 | #dfe6f3",
    "s 0 1.62 -.06 | .43 .27 .38 | #1b1b22",
    "k 0 1.64 .28 | .1 .12 .06 | #1b1b22 | 180 0 0",
    "E .16 1.46 .37 | .085 .095 .05 | #d81e38",
    "S .08 1.24 .37 | .025 .06 .02 | #ffffff",
    "b 0 1.29 .4 | .09 .015 .02 | #5a2030",
    "S:leg .18 .05 .1 | .12 .06 .18 | #1b1b22",
  ],
  "Carry Caravan": [
    "s 0 .82 -.1 | .5 .42 .66 | #d7a55f",
    "s 0 1.24 -.34 | .24 .24 .24 | #d7a55f",
    "s 0 1.24 .08 | .22 .22 .22 | #d7a55f",
    "c 0 1.3 .5 | .14 .34 .14 | #d7a55f | -20 0 0",
    "s 0 1.72 .62 | .26 .22 .3 | #d7a55f",
    "s 0 1.64 .86 | .16 .12 .14 | #f1d9b5",
    `E .16 1.81 .8 | .07 .085 .045 | ${INK}`,
    "S:ear .22 1.94 .52 | .07 .1 .04 | #d7a55f",
    "S:leg .3 .3 .3 | .09 .32 .09 | #c08f4a",
    "S:leg .3 .3 -.5 | .09 .32 .09 | #c08f4a",
    "b 0 1.06 -.12 | .52 .05 .3 | #2ec7c9",
    "S .56 .9 -.12 | .14 .2 .22 | #8a5a33",
    "c:wag 0 .86 -.78 | .03 .16 .03 | #c08f4a | -150 0 0",
  ],
  "Miner Mole": [
    "s 0 .62 0 | .54 .62 .48 | #5a4a52",
    "s 0 .56 .2 | .36 .42 .32 | #8c7a84",
    "s 0 1.3 .08 | .46 .4 .42 | #5a4a52",
    `k 0 1.2 .58 | .14 .2 .14 | ${PINK} | 90 0 0`,
    "s 0 1.2 .78 | .06 .06 .05 | #f4739a",
    `E .18 1.4 .43 | .07 .08 .045 | ${INK}`,
    `s 0 1.58 .02 | .44 .27 .42 | ${GOLD}`,
    "c 0 1.52 .1 | .48 .03 .48 | #e09a1b",
    `c 0 1.66 .42 | .09 .05 .09 | ${WHITE} | 90 0 0`,
    "s 0 1.66 .48 | .06 .06 .03 | #ffffaa!",
    `S:arm .6 .7 .2 | .16 .12 .14 | ${PINK}`,
    "c .75 .98 .24 | .03 .46 .03 | #8a5a33 | 0 0 -12",
    "b .83 1.42 .24 | .26 .05 .05 | #9aa3b5 | 0 0 -12",
    `S:leg .24 .07 .14 | .18 .08 .24 | ${PINK}`,
  ],
  "Crude Colossus": [
    "b 0 1 0 | .56 .5 .4 | #4a4f5e",
    "b 0 1.05 .38 | .34 .26 .05 | #c98a5a",
    "s 0 1.05 .44 | .12 .12 .06 | #ff9a3d!",
    "b 0 1.72 .04 | .28 .21 .25 | #5b6172",
    "S .12 1.75 .29 | .07 .05 .03 | #ffb054!",
    "b 0 1.61 .29 | .12 .02 .02 | #2a2d38",
    "S .78 1.36 0 | .26 .24 .26 | #5b6172",
    "S:arm .86 .82 .04 | .2 .42 .2 | #4a4f5e",
    "S+ .88 .34 .08 | .24 .2 .24 | #3b3f4c",
    "S:leg .28 .26 0 | .2 .28 .2 | #4a4f5e",
    "S+ .28 .06 .06 | .24 .08 .28 | #3b3f4c",
    "s .2 1.5 .34 | .06 .1 .04 | #1b1b22",
  ],
  "Market Maker": [
    "s 0 .14 0 | .3 .14 .3 | #2a2f45",
    "c 0 .7 0 | .46 .5 .46 | #dfe6f3",
    "c 0 .7 0 | .48 .08 .48 | #4a8cf7",
    "s 0 1.44 0 | .42 .36 .4 | #dfe6f3",
    "b 0 1.46 .31 | .32 .11 .09 | #1b2540",
    "s -.14 1.47 .39 | .065 .055 .02 | #35d49a!",
    "s .14 1.47 .39 | .065 .055 .02 | #ff6470!",
    "c 0 1.92 0 | .02 .14 .02 | #8e9bb6",
    `s:bob 0 2.08 0 | .06 .06 .06 | ${GOLD}!`,
    "S .72 1.02 0 | .3 .05 .05 | #8e9bb6",
    `S:tip 1 .86 0 | .22 .04 .22 | ${GOLD}`,
    "S+ 1 .93 0 | .1 .04 .1 | #e09a1b",
  ],
  "Fed Whisperer": [
    "s 0 .72 0 | .56 .7 .48 | #8a6a4a",
    "s 0 .64 .2 | .38 .48 .32 | #e9d7b8",
    "s 0 1.48 .04 | .52 .44 .44 | #8a6a4a",
    "S .21 1.5 .34 | .22 .22 .1 | #e9d7b8",
    "E .21 1.5 .42 | .14 .15 .06 | #e09a1b",
    "k 0 1.36 .48 | .07 .1 .07 | #e09a1b | 150 0 0",
    "K:ear .36 1.92 0 | .1 .16 .06 | #6b4f36 | 0 0 -25",
    "S:wing .58 .78 0 | .14 .44 .3 | #6b4f36 | 0 0 -10",
    `t .21 1.5 .5 | .17 .15 .17 | ${GOLD} | 90 0 0`,
    "S .09 1.08 .4 | .09 .06 .04 | #36c98f",
    "s 0 1.08 .42 | .04 .04 .03 | #1f8f68",
    "S:leg .2 .05 .16 | .12 .05 .16 | #e09a1b",
  ],
  "Flash Crash": [
    "s 0 1.7 0 | .5 .26 .36 | #6f7c99",
    "S .36 1.62 .05 | .28 .2 .26 | #5b6788",
    "s 0 1.84 -.05 | .3 .2 .26 | #8494b5",
    "b .1 1.25 .1 | .2 .22 .1 | #ffd23a! | 0 0 25",
    "b -.08 .86 .1 | .2 .22 .1 | #ffd23a! | 0 0 -25",
    "k .06 .4 .1 | .16 .3 .08 | #ffb300! | 180 0 12",
    `E .18 1.68 .33 | .085 .085 .05 | ${INK}`,
    "S .18 1.8 .36 | .1 .028 .03 | #2f3850 | 0 0 24",
    "s:bob .7 1 .2 | .06 .06 .06 | #fff3b0!",
    "s:bob -.66 .6 .1 | .05 .05 .05 | #fff3b0!",
  ],
  "Whale Watcher": [
    "s 0 .82 0 | .72 .62 .8 | #3f73c8",
    "s 0 .62 .14 | .6 .44 .7 | #dfe9f7",
    `E .43 .98 .57 | .1 .115 .055 | ${INK} | 0 35 0`,
    "b 0 .68 .8 | .2 .025 .03 | #1b2540",
    `S .56 .8 .5 | .08 .05 .04 | ${BLUSH}`,
    "S:wing .78 .56 .2 | .26 .06 .18 | #2f5aa6 | 0 0 -28",
    "s 0 .9 -.86 | .2 .16 .26 | #3f73c8",
    "S:wing .3 1.06 -1.06 | .26 .05 .16 | #2f5aa6 | 0 30 20",
    "c 0 1.56 .1 | .05 .14 .05 | #bfe3ff",
    "S:bob .16 1.78 .1 | .09 .09 .09 | #bfe3ff",
    "s:bob 0 1.9 .1 | .1 .1 .1 | #e8f6ff",
  ],
  "Black Swan": [
    "s 0 .6 -.1 | .56 .44 .7 | #1d2030",
    "S:wing .42 .74 -.2 | .2 .3 .5 | #2a2f45 | 0 0 -10",
    "k 0 .78 -.86 | .2 .26 .12 | #1d2030 | -60 0 0",
    "s 0 1 .42 | .16 .2 .16 | #1d2030",
    "s 0 1.3 .5 | .14 .2 .14 | #1d2030",
    "s 0 1.58 .44 | .14 .18 .14 | #1d2030",
    "s 0 1.8 .52 | .22 .2 .24 | #1d2030",
    "k 0 1.74 .82 | .08 .16 .07 | #e23b4a | 90 0 0",
    `s 0 1.78 .7 | .09 .07 .08 | ${WHITE}`,
    "E .13 1.87 .68 | .06 .065 .035 | #e23b4a",
    "S:leg .2 .2 0 | .04 .14 .04 | #3b3f4c",
    "S+ .2 .06 .1 | .14 .05 .2 | #3b3f4c",
    "t 0 1.14 .46 | .16 .3 .16 | #4a8cf7",
  ],
  "Central Banker": [
    "b 0 .92 0 | .6 .58 .46 | #6f7c99",
    "c 0 .86 .47 | .34 .03 .34 | #8e9bb6 | 90 0 0",
    `c 0 .86 .52 | .14 .04 .14 | ${GOLD} | 90 0 0`,
    "b 0 .86 .57 | .2 .03 .02 | #2a2f45",
    "b 0 .86 .57 | .03 .2 .02 | #2a2f45",
    `E .26 1.3 .46 | .1 .11 .045 | ${INK}`,
    "S .26 1.45 .47 | .11 .028 .02 | #2a2f45 | 0 0 -8",
    "c 0 1.78 0 | .3 .22 .3 | #1b1b22",
    "c 0 1.56 0 | .46 .03 .46 | #1b1b22",
    "c 0 1.62 0 | .31 .05 .31 | #36c98f",
    "S:arm .74 .9 0 | .1 .3 .1 | #5b6788 | 0 0 -16",
    `S+ .82 .56 0 | .12 .12 .12 | ${WHITE}`,
    "S:leg .28 .2 0 | .1 .2 .1 | #5b6788",
    "S+ .28 .05 .06 | .16 .07 .22 | #1b1b22",
  ],
  "Algo Overlord": [
    "b 0 .8 -.4 | .5 .62 .04 | #6a48c7 | 8 0 0",
    "b 0 .82 0 | .48 .5 .36 | #2a2f45",
    "c 0 .9 .37 | .16 .03 .16 | #b78cff! | 90 0 0",
    "b 0 1.56 .02 | .38 .28 .32 | #3b4160",
    "b 0 1.58 .32 | .32 .08 .04 | #b78cff!",
    `K .26 1.98 0 | .05 .16 .05 | ${GOLD}`,
    `k 0 2.04 0 | .06 .2 .06 | ${GOLD}`,
    "S .66 1.26 0 | .2 .16 .22 | #a070ff",
    "S:arm .72 .8 .02 | .12 .34 .12 | #3b4160",
    "S+ .74 .4 .04 | .15 .13 .15 | #6a48c7",
    "S:leg .24 .2 0 | .13 .22 .13 | #2a2f45",
    "S+ .24 .05 .05 | .17 .07 .22 | #3b4160",
    "S:bob .98 1.6 .1 | .09 .09 .09 | #d6bbff!",
  ],
};

/** What stands around the arena: statues of the bull and the bear, pylons, a coin and the bell. */
export const PROPS = {
  "Bull Statue": [
    `b 0 .12 0 | .5 .12 .76 | ${STONE}`,
    `b 0 .27 0 | .43 .04 .69 | ${STONE_LIGHT}`,
    `s 0 1 -.14 | .4 .4 .6 | ${BRONZE}`,
    `s 0 1.26 .2 | .37 .33 .34 | ${BRONZE}`,
    `s 0 1 .62 | .28 .28 .28 | ${BRONZE}`,
    `s 0 .86 .84 | .17 .14 .13 | ${BRONZE_DARK}`,
    "K .3 1.24 .64 | .07 .24 .07 | #f3e3b3 | 20 0 -62",
    "S .15 1.1 .85 | .04 .04 .03 | #ffe9a8!",
    `S .24 .54 .3 | .1 .25 .1 | ${BRONZE_DARK}`,
    `S .24 .54 -.5 | .1 .25 .1 | ${BRONZE_DARK}`,
    `c 0 1.22 -.76 | .03 .2 .03 | ${BRONZE_DARK} | -40 0 0`,
  ],
  "Bear Statue": [
    `b 0 .12 0 | .58 .12 .58 | ${STONE}`,
    `b 0 .27 0 | .5 .04 .5 | ${STONE_LIGHT}`,
    `s 0 1 0 | .46 .58 .4 | ${STEEL}`,
    `s 0 1.74 .08 | .34 .3 .32 | ${STEEL}`,
    `s 0 1.66 .36 | .16 .13 .13 | ${STEEL_DARK}`,
    `S .26 2 .02 | .11 .11 .06 | ${STEEL}`,
    `S .6 1.48 .1 | .13 .32 .13 | ${STEEL} | 0 0 -30`,
    `S .78 1.82 .12 | .14 .13 .13 | ${STEEL_DARK}`,
    `S .24 .52 .06 | .15 .22 .17 | ${STEEL_DARK}`,
    "S .12 1.82 .37 | .035 .035 .025 | #d6ecff!",
  ],
  Pylon: [
    `c 0 .1 0 | .36 .1 .36 | ${STONE}`,
    "c 0 .66 0 | .2 .48 .2 | #1f2a4a",
    "t 0 .5 0 | .27 .35 .27 | #58b6ff!",
    "t 0 .86 0 | .27 .35 .27 | #58b6ff!",
    `c 0 1.18 0 | .29 .05 .29 | ${STONE_LIGHT}`,
    "k 0 1.36 0 | .2 .14 .2 | #9fd4ff!",
  ],
  Coin: [
    `c 0 1 0 | .56 .07 .56 | ${GOLD} | 90 0 0`,
    "t 0 1 0 | .56 .45 .56 | #e09a1b | 90 0 0",
    "c 0 1 .07 | .4 .02 .4 | #ffe08a | 90 0 0",
    "c 0 1 -.07 | .4 .02 .4 | #ffe08a | 90 0 0",
    "b 0 .94 .1 | .05 .2 .02 | #c47f12",
    "k 0 1.22 .1 | .14 .1 .02 | #c47f12",
    "b 0 .94 -.1 | .05 .2 .02 | #c47f12",
    "k 0 1.22 -.1 | .14 .1 .02 | #c47f12",
  ],
  Bell: [
    `b 0 2.06 0 | .6 .05 .1 | ${STONE_LIGHT}`,
    "c 0 1.92 0 | .03 .12 .03 | #8e9bb6",
    `s 0 1.6 0 | .3 .26 .3 | ${GOLD}`,
    `c 0 1.38 0 | .33 .2 .33 | ${GOLD}`,
    `k 0 1.22 0 | .5 .24 .5 | ${GOLD}`,
    "t 0 1 0 | .52 .3 .52 | #e09a1b",
    "s 0 .9 0 | .1 .1 .1 | #8a5a14",
  ],
};

const COLOUR = /^#[0-9a-f]{6}!?$/i;
const KIND = /^([a-z])(?::([a-z]+)|(\+))?$/i;

/** Where each motion's pivot is on the part: the end the limb hangs or stands on. */
export const MOTION_ENDS = {
  arm: "top",
  leg: "top",
  ear: "bottom",
  wag: "bottom",
  wing: "inner",
  bob: "middle",
  tip: "middle",
};
const EYE_WHITE = [0.985, 0.98, 0.955];
const SHINE = [1, 1, 1];
const LID = [0.17, 0.13, 0.2];
const PUPIL = [0.08, 0.09, 0.14];
const DARK_IRIS = 0.12;

function numbers(text, count, spec) {
  const values = text.trim().split(/\s+/).map(Number);
  if (values.length !== count || values.some((value) => !Number.isFinite(value))) {
    throw new RangeError(`cannot read the part "${spec}"`);
  }
  return values;
}

/** "#rrggbb" as three numbers between 0 and 1. */
export function rgb(colour) {
  return [1, 3, 5].map((start) => parseInt(colour.slice(start, start + 2), 16) / 255);
}

/** The first word of a part: its kind, whether it is mirrored, its motion, whether it follows. */
function readKind(word, spec) {
  const [, letter, motion, plus] = KIND.exec(word) || [];
  const kind = letter && KINDS[letter.toLowerCase()];
  const known = !motion || Object.prototype.hasOwnProperty.call(MOTION_ENDS, motion);
  if (!kind || !known || (kind === "eye" && (motion || plus))) {
    throw new RangeError(`cannot read the part "${spec}"`);
  }
  return { kind, mirrored: letter !== letter.toLowerCase(), motion: motion || "", follows: Boolean(plus) };
}

/**
 * Split one part string into `{ kind, mirrored, motion, follows, at, size, colour, turn, glow }`.
 *
 * Throws a RangeError for a part it cannot read, so a typo never reaches the screen.
 */
export function parsePart(spec) {
  const fields = String(spec).split("|").map((field) => field.trim());
  const [word, ...place] = (fields[0] || "").split(/\s+/);
  const colour = fields[2] || "";
  if (fields.length < 3 || fields.length > 4 || !COLOUR.test(colour)) {
    throw new RangeError(`cannot read the part "${spec}"`);
  }
  return {
    ...readKind(word, spec),
    at: numbers(place.join(" "), 3, spec),
    size: numbers(fields[1], 3, spec),
    colour: rgb(colour),
    turn: fields.length === 4 ? numbers(fields[3], 3, spec) : [0, 0, 0],
    glow: colour.endsWith("!") ? 1 : 0,
  };
}

/** The mirror image of a part across x = 0. */
function mirror(part) {
  const [x, y, z] = part.at;
  const [rx, ry, rz] = part.turn;
  return { ...part, at: [-x, y, z], turn: [rx, -ry, -rz] };
}

/** A point given in a part's own turned frame, as a place in the figure. */
function placed(part, [x, y, z]) {
  const m = turnMatrix(part.turn);
  return [
    part.at[0] + m[0] * x + m[3] * y + m[6] * z,
    part.at[1] + m[1] * x + m[4] * y + m[7] * z,
    part.at[2] + m[2] * x + m[5] * y + m[8] * z,
  ];
}

/**
 * An eye as the balls it is drawn with. The irises of a pair turn a little towards each other
 * and the point of light sits on the same side in both, as light from one lamp would.
 * `when` says in which frames a part shows: the lid only when the figure blinks.
 */
export function eyeParts(eye) {
  const [wide, high, deep] = eye.size;
  const inward = -0.12 * wide * Math.sign(eye.at[0]);
  const ball = (at, size, colour, glow, when) => ({
    kind: "ball",
    at: placed(eye, at),
    size,
    colour,
    turn: eye.turn,
    glow,
    bare: true,
    when,
    motion: "",
    pivot: null,
  });
  const parts = [
    { ...ball([0, 0, 0], eye.size, EYE_WHITE, 0.55, "open"), bare: false },
    ball([inward, -0.04 * high, 0.52 * deep], [0.66 * wide, 0.72 * high, 0.6 * deep], eye.colour, 0.25, "open"),
  ];
  const [red, green, blue] = eye.colour;
  if (0.2126 * red + 0.7152 * green + 0.0722 * blue > DARK_IRIS) {
    parts.push(ball([inward, -0.04 * high, 0.82 * deep], [0.34 * wide, 0.38 * high, 0.34 * deep], PUPIL, 0, "open"));
  }
  parts.push(
    ball([-0.3 * wide, 0.32 * high, 1.02 * deep], [0.24 * wide, 0.24 * high, 0.16 * deep], SHINE, 1, "open"),
    ball([0, -0.06 * high, 0.3 * deep], [1.04 * wide, 0.2 * high, 0.9 * deep], LID, 0, "shut"),
  );
  return parts;
}

/** The point a limb turns about: the end of the part that its motion names. */
export function pivotOf(part) {
  const [wide, high] = part.size;
  const end = MOTION_ENDS[part.motion];
  if (end === "top" || end === "bottom") {
    return placed(part, [0, end === "top" ? high : -high, 0]);
  }
  if (end === "inner") {
    const ends = [placed(part, [wide, 0, 0]), placed(part, [-wide, 0, 0])];
    return Math.abs(ends[0][0]) <= Math.abs(ends[1][0]) ? ends[0] : ends[1];
  }
  return part.at;
}

/**
 * One side of a part as the studio draws it. `leads` remembers the last limb of each side, so
 * that a part which follows gets that limb's motion and pivot; a limb in the middle leads both.
 */
function solid(side, mirrored, follows, leads, spec) {
  const key = side.at[0] < 0 ? "left" : "right";
  let lead = null;
  if (follows) {
    lead = leads[key];
    if (!lead) {
      throw new RangeError(`the part "${spec}" has no limb to move with`);
    }
  } else if (side.motion) {
    lead = { motion: side.motion, pivot: pivotOf(side) };
    leads[key] = lead;
    if (!mirrored) {
      leads.left = lead;
      leads.right = lead;
    }
  }
  return { ...side, motion: lead ? lead.motion : "", pivot: lead ? lead.pivot : null, bare: false, when: "" };
}

/**
 * Every part that a list of part strings stands for: mirror images made, eyes taken apart,
 * limbs given the point they turn about.
 */
export function partsFrom(specs) {
  const leads = { left: null, right: null };
  return specs.flatMap((spec) => {
    const { mirrored, follows, ...part } = parsePart(spec);
    const sides = mirrored ? [part, mirror(part)] : [part];
    return sides.flatMap((side) =>
      side.kind === "eye" ? eyeParts(side) : [solid(side, mirrored, follows, leads, spec)],
    );
  });
}

/** Every part of a champion's figure; `null` for a name without one. */
export function partsOf(name) {
  return Object.prototype.hasOwnProperty.call(MODELS, name) ? partsFrom(MODELS[name]) : null;
}

/** Every part of something that stands in the arena; `null` for a name without one. */
export function propPartsOf(name) {
  return Object.prototype.hasOwnProperty.call(PROPS, name) ? partsFrom(PROPS[name]) : null;
}
