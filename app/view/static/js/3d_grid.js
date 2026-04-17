// Plotly-based 3D mesh diff renderer
// Input schema:
// {
//   nodes: { added: [nid], deleted: [nid], modified: { nid: {old,new,delta} } },
//   elements: { added: [eid], deleted: [eid], modified: {} },
//   materials: {...},
//   summary: { total_changes: N },
//   render: {
//     nodes: { old: {nid:[x,y,z]}, new: {nid:[x,y,z]} },
//     elements: { old: {eid:{type,node_ids}}, new: {eid:{type,node_ids}} }
//   }
// }

const COLOR_MAP = {
  same: '#484f58',
  added: '#3fb950',
  deleted: '#f85149',
  modified: '#d29922',
  adjacent: '#e5ff00a3',
};

function toIntIds(values) {
  return (values || []).map(v => Number(v)).filter(v => Number.isFinite(v));
}

function keyToIntMap(obj) {
  const out = new Map();
  Object.entries(obj || {}).forEach(([k, v]) => {
    const id = Number(k);
    if (Number.isFinite(id)) {
      out.set(id, v);
    }
  });
  return out;
}

function groupNodeIds(diffResult, oldNodesMap, newNodesMap) {
  const added = new Set(toIntIds(diffResult?.nodes?.added));
  const deleted = new Set(toIntIds(diffResult?.nodes?.deleted));
  const modified = new Set(
    Object.keys(diffResult?.nodes?.modified || {})
      .map(v => Number(v))
      .filter(v => Number.isFinite(v))
  );

  const same = [];
  const allCommon = new Set([...oldNodesMap.keys()].filter(id => newNodesMap.has(id)));
  allCommon.forEach(id => {
    if (!added.has(id) && !deleted.has(id) && !modified.has(id)) {
      same.push(id);
    }
  });

  return {
    same,
    added: [...added],
    deleted: [...deleted],
    modified: [...modified],
  };
}

function idsToCoords(ids, nodeMap, fallbackMap = null) {
  const x = [];
  const y = [];
  const z = [];
  const text = [];

  ids.forEach(id => {
    const xyz = nodeMap.get(id) || (fallbackMap ? fallbackMap.get(id) : null);
    if (!xyz || xyz.length < 3) return;
    x.push(xyz[0]);
    y.push(xyz[1]);
    z.push(xyz[2]);
    text.push(`NID ${id}`);
  });

  return { x, y, z, text };
}

function buildNodeTrace(status, ids, nodeMap, fallbackMap = null, customDataMap = null) {
  const coords = idsToCoords(ids, nodeMap, fallbackMap);
  if (!coords.x.length) return null;

  const trace = {
    type: 'scatter3d',
    mode: 'markers',
    name: `nodes-${status}`,
    showlegend: false,
    x: coords.x,
    y: coords.y,
    z: coords.z,
    text: coords.text,
    hovertemplate: '%{text}<extra></extra>',
    marker: {
      color: COLOR_MAP[status] || COLOR_MAP.same,
      size: status === 'modified' ? 5 : 4,
      opacity: status === 'same' ? 0.45 : 0.95,
    },
  };

  if (status === 'modified' && customDataMap) {
    const customdata = [];
    const hoverText = [];
    ids.forEach(id => {
      const entry = customDataMap[id];
      if (!entry) return;
      customdata.push(entry.delta || [0, 0, 0]);
      hoverText.push(
        `NID ${id}<br>old: [${(entry.old || []).join(', ')}]<br>new: [${(entry.new || []).join(', ')}]<br>delta: [${(entry.delta || []).join(', ')}]`
      );
    });
    if (hoverText.length) {
      trace.text = hoverText;
      trace.customdata = customdata;
      trace.hovertemplate = '%{text}<extra></extra>';
    }
  }

  return trace;
}

function triangulateElement(nodeIds) {
  if (!nodeIds || nodeIds.length < 3) return [];
  if (nodeIds.length === 3) return [[nodeIds[0], nodeIds[1], nodeIds[2]]];
  if (nodeIds.length >= 4) {
    return [
      [nodeIds[0], nodeIds[1], nodeIds[2]],
      [nodeIds[0], nodeIds[2], nodeIds[3]],
    ];
  }
  return [];
}

function buildMeshTrace(status, elementIds, elementMap, nodeMap, fallbackMap = null) {
  const x = [];
  const y = [];
  const z = [];
  const i = [];
  const j = [];
  const k = [];
  const facecolor = [];

  let idx = 0;
  elementIds.forEach(eid => {
    const elem = elementMap.get(eid);
    if (!elem) return;

    const triangles = triangulateElement(elem.node_ids || []);

    triangles.forEach(tri => {
      const pts = tri.map(nid => nodeMap.get(nid) || (fallbackMap ? fallbackMap.get(nid) : null));
      if (pts.some(p => !p || p.length < 3)) return;

      x.push(...pts.map(p => p[0]));
      y.push(...pts.map(p => p[1]));
      z.push(...pts.map(p => p[2]));

      i.push(idx);
      j.push(idx + 1);
      k.push(idx + 2);

      facecolor.push(COLOR_MAP[status] || COLOR_MAP.same);

      idx += 3;
    });
  });

  if (!x.length) return null;

  return {
    type: 'mesh3d',
    name: `elements-${status}`,
    showlegend: false,
    x,
    y,
    z,
    i,
    j,
    k,
    facecolor,
    opacity: status === 'same' ? 0.3 : 0.8,
  };
}

function findAdjacentElementIds(elementMap, modifiedNodeSet) {
  if (!modifiedNodeSet.size) return [];
  const adjacent = [];
  elementMap.forEach((elem, eid) => {
    const nodeIds = elem?.node_ids || [];
    if (nodeIds.some(nid => modifiedNodeSet.has(nid))) {
      adjacent.push(eid);
    }
  });
  return adjacent;
}

export function renderBdfGridDiff(containerId, diffResult) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!window.Plotly) {
    container.innerHTML = '<div class="text-danger p-3">Plotly failed to load.</div>';
    return;
  }

  const oldNodesMap = keyToIntMap(diffResult?.render?.nodes?.old);
  const newNodesMap = keyToIntMap(diffResult?.render?.nodes?.new);

  if (!oldNodesMap.size && !newNodesMap.size) {
    container.innerHTML = '<div class="text-muted p-3">No GRID nodes found for 3D rendering.</div>';
    return;
  }

  const oldElementsMap = keyToIntMap(diffResult?.render?.elements?.old);
  const newElementsMap = keyToIntMap(diffResult?.render?.elements?.new);

  const nodeGroups = groupNodeIds(diffResult, oldNodesMap, newNodesMap);

  const elementAdded = toIntIds(diffResult?.elements?.added);
  const elementDeleted = toIntIds(diffResult?.elements?.deleted);
  const elementModified = toIntIds(Object.keys(diffResult?.elements?.modified || {}));
  const changedNodeSet = new Set([...nodeGroups.modified, ...nodeGroups.added]);
  const adjacentNewElements = findAdjacentElementIds(newElementsMap, changedNodeSet);
  const adjacentElementSet = new Set(adjacentNewElements);

  const sameElements = [...newElementsMap.keys()].filter(
    eid => !elementAdded.includes(eid) && !elementDeleted.includes(eid) && !elementModified.includes(eid)
  );

  const traces = [];

  // Node scatter traces
  const sameNodeTrace = buildNodeTrace('same', nodeGroups.same, newNodesMap, oldNodesMap);
  const addedNodeTrace = buildNodeTrace('added', nodeGroups.added, newNodesMap, oldNodesMap);
  const deletedNodeTrace = buildNodeTrace('deleted', nodeGroups.deleted, oldNodesMap, newNodesMap);
  const modifiedNodeTrace = buildNodeTrace(
    'modified',
    nodeGroups.modified,
    newNodesMap,
    oldNodesMap,
    diffResult?.nodes?.modified || {}
  );

  [sameNodeTrace, addedNodeTrace, deletedNodeTrace, modifiedNodeTrace].forEach(t => {
    if (t) traces.push(t);
  });

  // Mesh traces
  const sameMesh = buildMeshTrace('same', sameElements, newElementsMap, newNodesMap, oldNodesMap);
  const addedMesh = buildMeshTrace('added', elementAdded, newElementsMap, newNodesMap, oldNodesMap);
  const deletedMesh = buildMeshTrace('deleted', elementDeleted, oldElementsMap, oldNodesMap, newNodesMap);
  const adjacentMesh = buildMeshTrace(
    'adjacent',
    [...adjacentElementSet],
    newElementsMap,
    newNodesMap,
    oldNodesMap
  );

  if (adjacentMesh) {
    adjacentMesh.name = 'elements-adjacent-highlight';
    adjacentMesh.opacity = 1.0;
    adjacentMesh.legendrank = 1;
    adjacentMesh.showlegend = true;
  }

  [sameMesh, addedMesh, deletedMesh, adjacentMesh].forEach(t => {
    if (t) traces.push(t);
  });

  const layout = {
    paper_bgcolor: '#1e1e1e',
    plot_bgcolor: '#1e1e1e',
    margin: { l: 0, r: 0, t: 20, b: 0 },
    scene: {
      bgcolor: '#1e1e1e',
      xaxis: { title: 'X', gridcolor: '#333', zerolinecolor: '#444' },
      yaxis: { title: 'Y', gridcolor: '#333', zerolinecolor: '#444' },
      zaxis: { title: 'Z', gridcolor: '#333', zerolinecolor: '#444' },
      camera: {
        eye: { x: 1.7, y: 1.3, z: 1.2 },
      },
      aspectmode: 'data',
    },
    legend: {
      orientation: 'v',
      yanchor: 'top',
      y: 0.98,
      xanchor: 'left',
      x: 0.02,
      bgcolor: 'rgba(30, 30, 30, 0.72)',
      bordercolor: '#3a3a3a',
      borderwidth: 1,
      font: { color: '#d4d4d4' },
    },
  };

  const config = {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['toImage'],
  };

  window.Plotly.newPlot(container, traces, layout, config);
}
