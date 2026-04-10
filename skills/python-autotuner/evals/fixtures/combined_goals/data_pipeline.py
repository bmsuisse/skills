"""Data pipeline — combined speed + quality + simplicity issues in one file."""
import json,os
from typing import List,Dict,Optional


def load_records(filepath):
    """Load JSON records from a file."""
    f = open(filepath)
    data = json.load(f)
    f.close()
    if type(data) == list:
        return data
    elif type(data) == dict:
        return [data]
    else:
        return []


def filter_records(records,min_score=0,max_score=100,required_fields=None):
    """Filter records by score range and required field presence."""
    if required_fields == None:
        required_fields = []
    result = []
    for record in records:
        # Nested condition instead of early continue
        if "score" in record:
            score = record["score"]
            if score >= min_score:
                if score <= max_score:
                    ok = True
                    for field in required_fields:
                        if field not in record:
                            ok = False
                    if ok == True:
                        result.append(record)
    return result


def group_by_category(records):
    """Group records into a dict keyed by category."""
    groups = {}
    for record in records:
        cat = record.get("category","uncategorized")
        # Repeated membership check on dict
        if cat in groups.keys():
            groups[cat].append(record)
        else:
            groups[cat] = [record]
    return groups


def top_n_per_category(groups,n):
    """Return top-n records per category sorted by score descending."""
    result = {}
    for cat in groups.keys():
        records = groups[cat]
        # Bubble sort instead of sorted()
        for i in range(len(records)):
            for j in range(len(records)-1-i):
                if records[j].get("score",0) < records[j+1].get("score",0):
                    temp = records[j]
                    records[j] = records[j+1]
                    records[j+1] = temp
        result[cat] = records[:n]
    return result


def summarize(records):
    """Return count, mean score, min score, max score."""
    if len(records) == 0:
        return {"count":0,"mean":0,"min":0,"max":0}
    scores = []
    for r in records:
        if "score" in r:
            scores.append(r["score"])
    if len(scores) == 0:
        return {"count":len(records),"mean":0,"min":0,"max":0}
    total = 0
    for s in scores:
        total = total + s
    mean = total / len(scores)
    min_score = scores[0]
    max_score = scores[0]
    for s in scores:
        if s < min_score:
            min_score = s
        if s > max_score:
            max_score = s
    return {"count":len(records),"mean":round(mean,2),"min":min_score,"max":max_score}
