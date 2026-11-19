import asyncio
from time import perf_counter

from policy import DECISION_MATRIX, decide_web

from .runtime import SCHEMAS
from .storage import now


class StepFailure(Exception):
    def __init__(self, code):
        self.code = code


def evidence_check(review, assessment):
    """Keep model output intact and qualify the verdict used by the policy."""
    by_id = {item["id"]: item for item in assessment["evidence"]}
    criteria = {f"S{i}" for i in range(1, len(assessment["success_criteria"]) + 1)}
    unknown_ids, invalid_criteria, grounded = set(), set(), set()
    direction = {"pass": "supports", "fail": "challenges"}.get(review["verdict"])
    for finding in review["findings"]:
        criterion = finding["criterion_id"]
        if criterion not in criteria:
            invalid_criteria.add(criterion)
        for evidence_id in finding["evidence_ids"]:
            item = by_id.get(evidence_id)
            if item is None:
                unknown_ids.add(evidence_id)
                continue
            compatible = item["criterion"] is None or f'S{item["criterion"]}' == criterion
            if compatible and item["status"] == "verified" and finding["stance"] == direction:
                grounded.add(criterion)
    enough = (bool(grounded & criteria) if direction == "challenges"
              else criteria.issubset(grounded))
    issues = []
    if unknown_ids:
        issues.append({"code": "invalid_citation", "values": sorted(unknown_ids)})
    if invalid_criteria:
        issues.append({"code": "invalid_criterion", "values": sorted(invalid_criteria)})
    if direction and not enough:
        issues.append({"code": "missing_verified_support", "values": []})
    if direction and any(item["status"] == "contradictory" for item in by_id.values()):
        issues.append({"code": "unresolved_contradiction", "values": []})
    return {"verdict": "unknown" if issues else review["verdict"], "issues": issues}


def compare(b, c, assessment):
    statements = []
    for idx, criterion in enumerate(assessment["success_criteria"], 1):
        cid = f"S{idx}"
        left = [item for item in b["findings"] if item["criterion_id"] == cid]
        right = [item for item in c["findings"] if item["criterion_id"] == cid]
        opposing = any({x["stance"], y["stance"]} == {"supports", "challenges"}
                       for x in left for y in right)
        statements.append({"criterion_id": cid, "criterion": criterion,
                           "B": left, "C": right, "possible_disagreement": opposing,
                           "contradictory_evidence": [
                               e["id"] for e in assessment["evidence"]
                               if e["status"] == "contradictory" and e["criterion"] in (None, idx)
                           ]})
    return statements


class Workflow:
    def __init__(self, store, runtime, timeout):
        self.store = store
        self.runtime = runtime
        self.timeout = timeout

    async def step(self, run, name, payload, round_number=None):
        agent = name if name in ("B", "C") else "A"
        entry = {"agent": agent, "step": name, "round": round_number, "status": "running",
                 "input": payload, "output": None, "model": self.runtime.model,
                 "usage": None, "duration_ms": None, "started_at": now()}
        run["audit"].append(entry)
        run["agents"][agent] = "running"
        self.store.save(run)
        start = perf_counter()
        try:
            result = await asyncio.wait_for(self.runtime.call(name, payload), self.timeout)
            output = SCHEMAS[name].model_validate(result.output).model_dump(mode="json")
            entry.update(output=output, model=result.model, usage=result.usage, status="complete")
            return output
        except TimeoutError:
            entry["status"] = "timed_out"
            raise StepFailure("agent_timeout") from None
        except asyncio.CancelledError:
            entry["status"] = "cancelled"
            raise
        except Exception:
            entry["status"] = "failed"
            raise StepFailure("agent_failed") from None
        finally:
            entry["duration_ms"] = round((perf_counter() - start) * 1000)
            run["agents"][agent] = entry["status"]
            self.store.save(run)

    async def parallel_round(self, run, shared, round_number, initial=None):
        payloads = {}
        for name, peer in (("B", "C"), ("C", "B")):
            payloads[name] = {**shared, "round": round_number}
            if initial:
                payloads[name].update(own_round_one=initial[name], peer_round_one=initial[peer])
        results = await asyncio.gather(
            *(self.step(run, name, payloads[name], round_number) for name in ("B", "C")),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                raise result
        return dict(zip(("B", "C"), results))

    async def execute(self, run, assessment):
        run["status"] = "running"
        self.store.save(run)
        try:
            frame = await self.step(run, "define", {"assessment": assessment})
            run["objective"] = frame
            # Submitted thresholds and criteria remain authoritative even if A rewrites them.
            shared = {"assessment": assessment, "framing": frame,
                      "criteria": {f"S{i}": value for i, value in enumerate(assessment["success_criteria"], 1)}}
            run["stage"] = "independent"
            first = await self.parallel_round(run, shared, 1)
            run["stage"] = "compare"
            run["initial_comparison"] = compare(first["B"], first["C"], assessment)
            self.store.save(run)
            reviews = first
            if assessment["cross_examine"]:
                run["stage"] = "cross_examine"
                reviews = await self.parallel_round(run, shared, 2, first)
            run["stage"] = "policy"
            run["comparison"] = compare(reviews["B"], reviews["C"], assessment)
            run["qualifications"] = {name: evidence_check(r, assessment) for name, r in reviews.items()}
            run["decision"] = decide_web(*(run["qualifications"][name]["verdict"] for name in ("B", "C")))
            self.store.save(run)
            run["stage"] = "synthesize"
            synthesis = await self.step(run, "synthesize", {
                **shared, "round_one": first, "latest_reviews": reviews,
                "comparison": run["comparison"], "qualifications": run["qualifications"],
                "decision": run["decision"],
            })
            run.update(status="complete", stage="report", report={
                "version": 1, "run_id": run["id"], "mode": run["mode"],
                "assessment": assessment, "framing": frame, "synthesis": synthesis,
                "sufficiency": reviews["B"], "necessity": reviews["C"],
                "evidence_matrix": run["comparison"], "initial_comparison": run["initial_comparison"],
                "decision": run["decision"], "decision_matrix": DECISION_MATRIX,
                "qualifications": run["qualifications"],
                "audit": run["audit"],
            })
        except asyncio.CancelledError:
            run["status"] = "cancelled"
        except StepFailure as exc:
            run.update(status="failed", error=exc.code)
        except Exception:
            # Exception strings may contain SDK request or document data.
            run.update(status="failed", error="workflow_failed")
        finally:
            run["finished_at"] = now()
            self.store.save(run)
