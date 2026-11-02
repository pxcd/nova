// Apple fm serve rejects JSON Schema unions and properties without a type.
// Narrow only known HA fields to representations HA already accepts.
export function normalizeFmRequest(request) {
  const result = structuredClone(request);
  for (const tool of result.tools || []) {
    const { name, parameters } = tool.function;
    const properties = parameters?.properties || {};
    if (name === 'homeassistant__GetLiveContext' && properties.domain?.anyOf) {
      const array = properties.domain.anyOf.find(schema => schema.type === 'array');
      if (array) properties.domain = { ...array, description: properties.domain.description };
    }
    if (name === 'media_player__HassSetVolumeRelative' && properties.volume_step?.anyOf) {
      const integer = properties.volume_step.anyOf.find(schema => schema.type === 'integer');
      if (integer) properties.volume_step = { ...integer, description: 'Signed volume percentage adjustment: positive raises volume, negative lowers it.' };
    }
    if (['media_player__HassMediaPlayerMute', 'media_player__HassMediaPlayerUnmute'].includes(name)
        && properties.is_volume_muted && !properties.is_volume_muted.type) {
      properties.is_volume_muted.type = 'boolean';
    }
    checkSchema(parameters, name);
  }
  return result;
}

function checkSchema(schema, path) {
  if (!schema || typeof schema.type !== 'string' || schema.anyOf || schema.oneOf || schema.allOf || schema.$ref) {
    throw new TypeError(`Unsupported Apple FM tool schema at ${path}; no request was forwarded.`);
  }
  for (const [name, property] of Object.entries(schema.properties || {})) checkSchema(property, `${path}.${name}`);
  if (schema.items) checkSchema(schema.items, `${path}[]`);
}
