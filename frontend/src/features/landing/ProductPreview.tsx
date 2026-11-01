import { useState } from "react";
import { Link } from "react-router-dom";

import { Tabs } from "@/components/Tabs";

const PREVIEWS = [
  { id: "problem", label: "Understand the problem" },
  { id: "code", label: "Write your solution" },
  { id: "coach", label: "Find your next step" },
] as const;

export function ProductPreview() {
  const [view, setView] = useState<"problem" | "code" | "coach">("code");
  return (
    <section className="product-preview" aria-label="Workspace preview">
      <div className="product-preview__bar">
        <span className="product-preview__title"><span className="product-preview__dot" />codecoach / workspace</span>
        <span className="badge">Interactive tour</span>
      </div>
      <Tabs label="Product tour" tabs={PREVIEWS} value={view} onChange={setView} panelClassName="product-preview__body">
        <div className="product-preview__statement">
          <span className="eyebrow">01 / The challenge</span>
          <h2>Two Sum</h2>
          <div className="row"><span className="badge badge--difficulty-easy">Easy</span><span className="topic-tag">arrays</span><span className="topic-tag">hash-maps</span></div>
          <p>Find two numbers that add up to a target. Return their indices.</p>
          <div className="product-preview__example"><span className="subtle">Example input</span><code>nums = [2, 7, 11, 15]<br />target = 9</code></div>
          <Link to="/problems/two-sum">Explore this problem <span aria-hidden="true">→</span></Link>
        </div>
        <div className="product-preview__detail" aria-live="polite">
          {view === "problem" ? <>
            <div className="product-preview__file">Your starting point</div>
            <h3>Get the contract right.</h3>
            <p>Read the statement, check the constraints, and reason through a small example before you code.</p>
            <div className="example"><span className="subtle">Example output</span><code>[0, 1]</code><p className="subtle">The numbers at these indices are 2 and 7. Their sum is 9.</p></div>
          </> : view === "code" ? <>
            <div className="product-preview__file"><span>Solution.java</span><span>Java 21</span></div>
            <pre className="product-preview__code"><code><span className="syntax-keyword">class</span>{` Solution {
  `}<span className="syntax-keyword">public</span>{` int[] twoSum(
      int[] nums, int target) {

    `}<span className="syntax-comment">// Make room for your approach.</span>{`
    `}<span className="syntax-keyword">return</span>{` new int[0];
  }
}`}</code></pre>
            <div className="product-preview__status"><span>Autosaved drafts · Java syntax</span><kbd>⌘ / Ctrl + Enter</kbd></div>
          </> : <>
            <div className="product-preview__file">The coaching ladder</div>
            <h3>Just enough help to move forward.</h3>
            <ol className="tour-ladder"><li><span>01</span><div><strong>Nudge</strong><p>A small prompt to get unstuck.</p></div></li><li><span>02</span><div><strong>Concept</strong><p>The idea behind an effective approach.</p></div></li><li><span>03</span><div><strong>Pseudocode</strong><p>A structure you can turn into Java.</p></div></li><li><span>04</span><div><strong>Explanation</strong><p>The full reasoning, when you need it.</p></div></li></ol>
          </>}
        </div>
      </Tabs>
      <p className="product-preview__caption">Example workspace. Open a problem to write code, request real coaching, and submit to the configured judge.</p>
    </section>
  );
}
