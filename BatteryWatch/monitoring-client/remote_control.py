"""Narrow SNMP write path for explicitly approved remote charge-limit commands."""
from pysnmp.hlapi import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, getCmd, setCmd,
)
from pysnmp.proto.rfc1902 import Unsigned32


CHARGE_LIMIT_OID = '1.3.6.1.4.1.2011.6.164.1.17.2.1.13.96'


def apply_charge_limit(config, command):
    command_id = command.get('command_id')
    value = command.get('value_centi')
    if (command.get('action') != 'charge_current_limit'
            or not isinstance(command_id, str)
            or type(value) is not int
            or not 5 <= value <= 100):
        return dict(command_id=command_id, status='failed',
                    applied_value_centi=None, message='잘못된 원격 설정 명령')
    if not all(config.get(key) for key in ('ip', 'get_community', 'set_community')):
        return dict(command_id=command_id, status='failed',
                    applied_value_centi=None, message='장비 SNMP 설정이 완료되지 않았습니다.')

    engine = SnmpEngine()
    target = UdpTransportTarget(
        (config['ip'], int(config.get('port') or 161)), timeout=2, retries=1)
    try:
        indication, status, _, _ = next(setCmd(
            engine, CommunityData(config['set_community'], mpModel=1), target,
            ContextData(), ObjectType(ObjectIdentity(CHARGE_LIMIT_OID), Unsigned32(value))))
        if indication or status:
            return dict(command_id=command_id, status='failed',
                        applied_value_centi=None, message='장비에서 설정 명령을 거부했습니다.')

        indication, status, _, bindings = next(getCmd(
            engine, CommunityData(config['get_community'], mpModel=1), target,
            ContextData(), ObjectType(ObjectIdentity(CHARGE_LIMIT_OID))))
        if indication or status or not bindings:
            return dict(command_id=command_id, status='failed',
                        applied_value_centi=None, message='설정 후 장비 값을 확인하지 못했습니다.')

        applied = int(bindings[0][1])
        if applied != value:
            return dict(command_id=command_id, status='failed',
                        applied_value_centi=applied if 5 <= applied <= 100 else None,
                        message='설정값과 장비 확인값이 일치하지 않습니다.')
        return dict(command_id=command_id, status='succeeded',
                    applied_value_centi=applied, message='장비 설정 및 GET 확인 완료')
    except (OSError, TypeError, ValueError, StopIteration):
        return dict(command_id=command_id, status='failed',
                    applied_value_centi=None, message='장비 SNMP 통신 또는 확인에 실패했습니다.')
    finally:
        dispatcher = getattr(engine, 'transportDispatcher', None)
        if dispatcher is not None:
            dispatcher.closeDispatcher()
