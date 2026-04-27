from __future__ import annotations

from ...exceptions import ValidationError


def normalize_strategy_params(definition: dict, params: dict) -> dict:
    if not isinstance(params, dict):
        raise ValidationError('策略参数必须是对象')
    normalized = dict(definition['defaultParams'])
    normalized.update(params)
    schema_by_field = {item['field']: item for item in definition['paramSchema']}
    extra_fields = sorted(set(normalized.keys()) - set(schema_by_field.keys()))
    if extra_fields:
        raise ValidationError(f"存在未定义的策略参数：{', '.join(extra_fields)}")
    for field_name, schema in schema_by_field.items():
        if schema.get('required') and field_name not in normalized:
            raise ValidationError(f'缺少必填策略参数：{field_name}')
        value = normalized.get(field_name)
        field_type = schema.get('type')
        if field_type == 'boolean':
            if not isinstance(value, bool):
                raise ValidationError(f'策略参数 {field_name} 必须是布尔值')
        elif field_type == 'integer':
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValidationError(f'策略参数 {field_name} 必须是整数')
        elif field_type == 'number':
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValidationError(f'策略参数 {field_name} 必须是数字')
        else:
            raise ValidationError(f'不支持的策略参数类型：{field_type}')
        if 'min' in schema and value < schema['min']:
            raise ValidationError(f"策略参数 {field_name} 不能小于 {schema['min']}")
        if 'max' in schema and value > schema['max']:
            raise ValidationError(f"策略参数 {field_name} 不能大于 {schema['max']}")
    return normalized
