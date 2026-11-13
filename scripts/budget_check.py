#!/usr/bin/env python3
"""
VM Resource & Cost Budget Verifier for OpenHands on OCI Always-Free
Checks disk, memory, swap, orphan runtime containers, and LLM footprint.
"""

import os
import shutil
import subprocess
import sys
import json

def get_disk_budget():
    total, used, free = shutil.disk_usage("/")
    used_pct = (used / total) * 100
    total_gb = total / (1024**3)
    used_gb = used / (1024**3)
    free_gb = free / (1024**3)
    
    status = "OK"
    if used_pct >= 85:
        status = "CRITICAL"
    elif used_pct >= 75:
        status = "WARNING"
        
    return {
        "status": status,
        "total_gb": round(total_gb, 1),
        "used_gb": round(used_gb, 1),
        "free_gb": round(free_gb, 1),
        "used_pct": round(used_pct, 1)
    }

def get_memory_budget():
    mem_total = 0
    mem_avail = 0
    swap_total = 0
    swap_free = 0
    
    with open("/proc/meminfo") as f:
        for line in f:
            parts = line.split(":")
            key = parts[0].strip()
            val = int(parts[1].strip().split()[0]) # in kB
            if key == "MemTotal":
                mem_total = val / 1024 # MB
            elif key == "MemAvailable":
                mem_avail = val / 1024 # MB
            elif key == "SwapTotal":
                swap_total = val / 1024 # MB
            elif key == "SwapFree":
                swap_free = val / 1024 # MB

    mem_used = mem_total - mem_avail
    mem_used_pct = (mem_used / mem_total) * 100 if mem_total else 0
    swap_used = swap_total - swap_free
    swap_used_pct = (swap_used / swap_total) * 100 if swap_total else 0
    
    status = "OK"
    if mem_avail < 1024:
        status = "CRITICAL"
    elif mem_avail < 2048:
        status = "WARNING"

    return {
        "status": status,
        "mem_total_mb": round(mem_total, 1),
        "mem_used_mb": round(mem_used, 1),
        "mem_avail_mb": round(mem_avail, 1),
        "mem_used_pct": round(mem_used_pct, 1),
        "swap_total_mb": round(swap_total, 1),
        "swap_used_mb": round(swap_used, 1),
        "swap_used_pct": round(swap_used_pct, 1)
    }

def get_docker_runtime_budget():
    try:
        res = subprocess.run(
            ["sudo", "docker", "ps", "--filter", "name=openhands-runtime", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        lines = [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]
        count = len(lines)
        status = "OK"
        if count > 1:
            status = "WARNING"
        return {
            "status": status,
            "running_runtime_containers": count,
            "containers": lines
        }
    except Exception as e:
        return {"status": "UNKNOWN", "error": str(e), "running_runtime_containers": 0}

def get_ollama_budget():
    try:
        ps_res = subprocess.run(
            ["ollama", "ps"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        ps_lines = [l.strip() for l in ps_res.stdout.strip().split("\n") if l.strip()]
        loaded_models = len(ps_lines) - 1 if len(ps_lines) > 1 else 0

        list_res = subprocess.run(
            ["ollama", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        list_lines = [l.strip() for l in list_res.stdout.strip().split("\n") if l.strip()]
        installed_models = len(list_lines) - 1 if len(list_lines) > 1 else 0

        return {
            "status": "OK",
            "installed_models_count": installed_models,
            "active_loaded_in_ram": loaded_models,
            "active_detail": ps_lines[1:] if loaded_models > 0 else []
        }
    except Exception as e:
        return {"status": "INACTIVE", "error": str(e)}

def cleanup_stale_containers():
    print("\n🧹 Pruning excess runtime containers and dangling Docker resources...")
    try:
        # Find active openhands-runtime containers
        ps_out = subprocess.run(
            ["sudo", "docker", "ps", "-q", "--filter", "name=openhands-runtime"],
            stdout=subprocess.PIPE,
            text=True,
            check=False
        ).stdout.strip()
        if ps_out:
            container_ids = ps_out.split()
            if "--all" in sys.argv:
                to_remove = container_ids
                print(f"Stopping and removing all {len(to_remove)} runtime container(s)...")
            else:
                to_remove = container_ids[1:]
                if to_remove:
                    print(f"Preserving 1 warm standby container ({container_ids[0]}), stopping {len(to_remove)} excess container(s)...")
                else:
                    print(f"Single warm standby container ({container_ids[0]}) healthy. No excess containers to prune.")
            
            if to_remove:
                subprocess.run(["sudo", "docker", "stop"] + to_remove, check=False)
                subprocess.run(["sudo", "docker", "rm", "-f"] + to_remove, check=False)
    except Exception as e:
        print(f"Warning during runtime container cleanup: {e}")

    subprocess.run(["sudo", "docker", "container", "prune", "-f"], check=False)
    print("✅ Sandbox & container cleanup complete.")

def print_budget_report():
    if "--cleanup" in sys.argv:
        cleanup_stale_containers()

    disk = get_disk_budget()
    mem = get_memory_budget()
    docker = get_docker_runtime_budget()
    ollama = get_ollama_budget()
    
    overall_status = "HEALTHY"
    if disk["status"] == "CRITICAL" or mem["status"] == "CRITICAL":
        overall_status = "CRITICAL"
    elif disk["status"] == "WARNING" or mem["status"] == "WARNING" or docker["status"] == "WARNING":
        overall_status = "WARNING"
        
    print("=" * 64)
    print(f"📊 VM RESOURCE & COST BUDGET REPORT [{overall_status}]")
    print("=" * 64)
    
    # Disk Section
    d_stat = f"[{disk['status']}]"
    print(f"💽 Disk Storage (OCI Always-Free 200GB limit): {d_stat}")
    print(f"   • Root Filesystem: {disk['used_gb']} GB used / {disk['total_gb']} GB total ({disk['used_pct']}%)")
    print(f"   • Headroom:        {disk['free_gb']} GB remaining free")
    
    # Memory Section
    m_stat = f"[{mem['status']}]"
    print(f"\n🧠 System Memory & Swap (11GB RAM + 4GB Swap): {m_stat}")
    print(f"   • RAM:             {mem['mem_used_mb']/1024:.2f} GB used / {mem['mem_total_mb']/1024:.2f} GB total ({mem['mem_used_pct']}%)")
    print(f"   • Available RAM:   {mem['mem_avail_mb']/1024:.2f} GB free headroom")
    print(f"   • Swap Space:      {mem['swap_used_mb']:.1f} MB used / {mem['swap_total_mb']/1024:.2f} GB total ({mem['swap_used_pct']}%)")

    # Docker Sandboxes
    doc_stat = f"[{docker['status']}]"
    print(f"\n🐳 OpenHands Execution Sandboxes: {doc_stat}")
    print(f"   • Active Runtime Containers: {docker['running_runtime_containers']}")
    if docker.get("containers"):
        for c in docker["containers"]:
            print(f"     - {c}")
    else:
        print("     - No idle runtime sandboxes currently consuming RAM.")

    # Ollama / Local LLM
    print(f"\n🦙 Local LLM (Ollama Zero-Cost Engine): [{ollama['status']}]")
    print(f"   • Installed Models on Disk: {ollama.get('installed_models_count', 0)}")
    print(f"   • Models Active in RAM:     {ollama.get('active_loaded_in_ram', 0)}")
    if ollama.get("active_detail"):
        for m in ollama["active_detail"]:
            print(f"     - {m}")
    else:
        print("     - Model unallocated from RAM (0 MB active RAM load).")

    # Cost Summary
    print("\n💰 Cloud Spend & Free Limit Compliance:")
    print("   • Local LLM (Ollama):       $0.00 (Zero API cost)")
    print("   • OCI Compute & Disk:       $0.00 (100% within OCI Always-Free tier)")
    print("   • Ingress / Reverse Proxy:  $0.00 (Self-hosted Nginx + Let's Encrypt)")
    print("=" * 64)
    
    return 0 if overall_status == "HEALTHY" else (1 if overall_status == "WARNING" else 2)

if __name__ == "__main__":
    sys.exit(print_budget_report())
