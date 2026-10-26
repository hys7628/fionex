"""개발용 기준 관리 명령(사용자 API·화면 아님). 저장소 루트에서 실행:

    python -m features.green_claim.criteria_admin status
    python -m features.green_claim.criteria_admin check            # 공식 출처 조회(네트워크, 제한 적용)
    python -m features.green_claim.criteria_admin prepare <후보>   # 활성 기준 자료를 후보 폴더로 복사
    python -m features.green_claim.criteria_admin build <후보> --version <묶음 버전>
    python -m features.green_claim.criteria_admin validate <후보>
    python -m features.green_claim.criteria_admin activate <후보>  # 검토 기록(review.json)이 있어야 함
    python -m features.green_claim.criteria_admin rollback
    python -m features.green_claim.criteria_admin unlock --force

후보 이름만 받으며 임의 경로를 받지 않습니다. 결과는 JSON으로 출력하고 오류는 고정 문장·code만 출력합니다.
사용법과 실패 시 조치: features/green_claim/data/README.md
"""
import argparse
import json
import sys

from features.green_claim import criteria_build as cb
from features.green_claim import criteria_check as cc
from features.green_claim import criteria_loader as cl
from features.green_claim import criteria_store as cs


def _print(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="criteria_admin", description="그린 클레임 기준 자료 관리(개발용)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="활성 기준과 마지막 확인 상태(네트워크 없음)")
    commands.add_parser("check", help="고정 공식 출처 확인(네트워크, 요청당 10초·전체 30초·출처별 2요청·5,000,000바이트)")
    for name in ("prepare", "validate", "activate"):
        commands.add_parser(name).add_argument("candidate")
    build = commands.add_parser("build")
    build.add_argument("candidate")
    build.add_argument("--version", required=True, help="자체 묶음 버전(예: 2026-11-01.1)")
    commands.add_parser("rollback", help="포인터의 previous 버전으로 되돌리기")
    unlock = commands.add_parser("unlock", help="남은 잠금 파일 삭제")
    unlock.add_argument("--force", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            _print(cc.criteria_status())
        elif args.command == "check":
            _print(cc.check_sources())
        elif args.command == "prepare":
            path = cs.prepare_candidate(args.candidate)
            _print({"prepared": args.candidate, "files": sorted(p.name for p in path.iterdir()),
                    "next": "md·sources_meta.json을 검토해 고친 뒤 build → validate → review.json 작성 → activate"})
        elif args.command == "build":
            loaded = cb.build_candidate(args.candidate, args.version)
            _print({"built": args.candidate, "bundle": loaded["bundle"], "counts": loaded["counts"]})
        elif args.command == "validate":
            _print(cs.validate_candidate(args.candidate))
        elif args.command == "activate":
            _print(cs.activate_candidate(args.candidate))
        elif args.command == "rollback":
            _print(cs.rollback())
        elif args.command == "unlock":
            _print({"removed": cs.force_unlock()})
    except cl.CriteriaError as err:
        _print({"error": err.to_dict(), "detail": err.detail})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
