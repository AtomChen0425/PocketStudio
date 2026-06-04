"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Connection,
  type Edge,
  type EdgeChange,
  type EdgeProps,
  type EdgeTypes,
  type Node,
  type NodeChange,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import { Check, CircleDot, FileJson, GitBranch, LayoutDashboard, Plus, Square, Trash2, Upload, Wand2, Wrench } from "lucide-react";

import { agentColor } from "@/components/sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type {
  AgentConfig,
  WorkflowConditionalEdge,
  WorkflowDefinition,
  WorkflowEdge,
  WorkflowNode,
  WorkflowRoute,
  WorkflowRoutingFunction,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type EditorMode = "graph" | "json";

type WorkflowEditorProps = {
  enabled: boolean;
  workflowId: string;
  workflowName: string;
  definitionJson: string;
  agents: Record<string, AgentConfig>;
  teamAgentIds: string[];
  leaderAgentId: string;
  onEnabledChange: (enabled: boolean) => void;
  onWorkflowIdChange: (workflowId: string) => void;
  onWorkflowNameChange: (workflowName: string) => void;
  onDefinitionJsonChange: (json: string) => void;
  onValidateDefinition: (definition: WorkflowDefinition) => Promise<void>;
};

type WorkflowNodeData = {
  workflowNode: WorkflowNode;
  label: string;
  color: string;
  isEntry: boolean;
  isOutput: boolean;
};

type WorkflowEdgeData = {
  conditional?: boolean;
  condition?: string;
  lane?: number;
  backEdge?: boolean;
};

const FLOW_NODE_WIDTH = 190;
const FLOW_NODE_HEIGHT = 95;
const EDGE_LANE_GAP = 34;

function defaultRoutingFunction(source: string, routes: WorkflowRoute[] = []): WorkflowRoutingFunction {
  const firstRoute = routes[0]?.condition || "condition_1";
  const fallbackRoute = routes[1]?.condition || firstRoute;
  return {
    language: "python",
    entrypoint: "route",
    code: [
      "def route(state):",
      `    output = state.get("outputs", {}).get("${source}", "")`,
      `    if "${firstRoute}" in output:`,
      `        return "${firstRoute}"`,
      `    return "${fallbackRoute}"`,
    ].join("\n"),
  };
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function defaultDefinition(agentId: string): WorkflowDefinition {
  const nodes: WorkflowNode[] = [
    { id: "start", type: "start", prompt: "Workflow input" },
    { id: "end", type: "end", prompt: "Workflow output" },
  ];
  const edges: WorkflowEdge[] = [];
  if (agentId) {
    nodes.splice(1, 0, {
      id: "agent_1",
      type: "agent",
      agentId,
      prompt: "Handle the team request.",
    });
  }
  return {
    version: 1,
    entrypoint: "start",
    outputNode: "end",
    nodes,
    edges,
    metadata: { name: "Default Workflow" },
  };
}

function parseDefinition(value: unknown): WorkflowDefinition {
  if (!value || typeof value !== "object") {
    throw new Error("Workflow JSON must be an object");
  }
  const record = value as Record<string, unknown>;
  const workflow = record.workflow && typeof record.workflow === "object"
    ? record.workflow as Record<string, unknown>
    : record;
  const definition = workflow.definition && typeof workflow.definition === "object"
    ? workflow.definition
    : workflow;
  const candidate = definition as Partial<WorkflowDefinition>;
  if (!candidate.entrypoint || !Array.isArray(candidate.nodes)) {
    throw new Error("Workflow JSON must include entrypoint and nodes");
  }
  return normalizeDefinition({
    version: candidate.version ?? 1,
    entrypoint: candidate.entrypoint,
    outputNode: candidate.outputNode || "",
    nodes: candidate.nodes as WorkflowNode[],
    edges: Array.isArray(candidate.edges) ? candidate.edges as WorkflowEdge[] : [],
    conditionalEdges: Array.isArray(candidate.conditionalEdges)
      ? candidate.conditionalEdges as WorkflowConditionalEdge[]
      : [],
    metadata: candidate.metadata || {},
  });
}

function parseDefinitionJson(json: string, fallbackAgentId: string): WorkflowDefinition {
  if (!json.trim()) return defaultDefinition(fallbackAgentId);
  return parseDefinition(JSON.parse(json));
}

function normalizeDefinition(definition: WorkflowDefinition): WorkflowDefinition {
  const originalNodes = definition.nodes.map((node) => ({
    ...node,
    type: node.type || "agent",
    agentId: node.agentId || "",
    prompt: node.prompt || "",
    inputTemplate: node.inputTemplate || "",
  }));
  const nodeIdSet = new Set(originalNodes.map((node) => node.id));
  const existingStart = originalNodes.find((node) => node.type === "start");
  const existingEnd = originalNodes.find((node) => node.type === "end");
  const startId = existingStart?.id || uniqueNodeId(nodeIdSet, "start");
  if (!existingStart) nodeIdSet.add(startId);
  const endId = existingEnd?.id || uniqueNodeId(nodeIdSet, "end");
  const nodes = [
    ...(existingStart ? [] : [{ id: startId, type: "start", prompt: "Workflow input", agentId: "", inputTemplate: "" }]),
    ...originalNodes,
    ...(existingEnd ? [] : [{ id: endId, type: "end", prompt: "Workflow output", agentId: "", inputTemplate: "" }]),
  ];
  const nodeIds = new Set(nodes.map((node) => node.id));
  const entrypoint = startId;
  const outputNode = endId;
  const edges = (definition.edges || []).filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));
  const conditionalEdges = (definition.conditionalEdges || [])
    .map((conditionalEdge) => ({
      source: conditionalEdge.source,
      routes: conditionalEdge.routes.filter((route) => route.condition && nodeIds.has(route.target)),
    }))
    .filter((conditionalEdge) => nodeIds.has(conditionalEdge.source) && conditionalEdge.routes.length > 0);
  return {
    version: definition.version ?? 1,
    entrypoint,
    outputNode,
    nodes,
    edges,
    conditionalEdges,
    metadata: definition.metadata || {},
  };
}

function uniqueNodeId(existing: Set<string>, base: string): string {
  if (!existing.has(base)) return base;
  let index = 1;
  while (existing.has(`${base}_${index}`)) index += 1;
  return `${base}_${index}`;
}

function definitionToFlow(
  definition: WorkflowDefinition,
  agents: Record<string, AgentConfig>,
): { nodes: Node<WorkflowNodeData>[]; edges: Edge<WorkflowEdgeData>[] } {
  const positions = layoutPositions(definition);
  const nodes = definition.nodes.map((workflowNode, index) => ({
    id: workflowNode.id,
    type: "workflowAgent",
    position: positions.get(workflowNode.id) || { x: index * (FLOW_NODE_WIDTH + 120), y: 80 },
    data: {
      workflowNode,
      label: workflowNode.type === "start"
        ? "Start"
        : workflowNode.type === "end"
          ? "End"
          : workflowNode.type === "tool"
            ? workflowNode.id
            : agents[workflowNode.agentId || ""]?.name || workflowNode.agentId || workflowNode.id,
      color: workflowNode.type === "agent" ? agentColor(workflowNode.agentId || "") : "bg-muted-foreground",
      isEntry: workflowNode.id === definition.entrypoint,
      isOutput: workflowNode.id === definition.outputNode,
    },
  }));
  const edgeLane = makeEdgeLaneResolver(definition, positions);
  const normalEdges: Edge<WorkflowEdgeData>[] = definition.edges.map((edge) => ({
    id: `${edge.source}->${edge.target}`,
    source: edge.source,
    target: edge.target,
    type: "workflow",
    animated: false,
    style: { stroke: "var(--color-primary)" },
    data: {
      conditional: false,
      lane: edgeLane(edge.source, edge.target),
      backEdge: isBackEdge(edge.source, edge.target, positions),
    },
  }));
  const conditionalEdges: Edge<WorkflowEdgeData>[] = (definition.conditionalEdges || []).flatMap((conditionalEdge) =>
    conditionalEdge.routes.map((route) => ({
      id: `${conditionalEdge.source}->${route.target}:${route.condition}`,
      source: conditionalEdge.source,
      target: route.target,
      type: "workflow",
      label: route.condition,
      animated: false,
      style: { stroke: "var(--color-primary)", strokeDasharray: "6 4" },
      data: {
        conditional: true,
        condition: route.condition,
        lane: edgeLane(conditionalEdge.source, route.target),
        backEdge: isBackEdge(conditionalEdge.source, route.target, positions),
      },
    }))
  );
  return { nodes, edges: [...normalEdges, ...conditionalEdges] };
}

function isBackEdge(source: string, target: string, positions: Map<string, { x: number; y: number }>): boolean {
  const sourcePosition = positions.get(source);
  const targetPosition = positions.get(target);
  if (!sourcePosition || !targetPosition) return false;
  return targetPosition.x <= sourcePosition.x + FLOW_NODE_WIDTH / 2;
}

function makeEdgeLaneResolver(
  definition: WorkflowDefinition,
  positions: Map<string, { x: number; y: number }>,
): (source: string, target: string) => number {
  const edgeCounts = new Map<string, number>();
  for (const edge of allGraphEdges(definition)) {
    const key = edge.source;
    edgeCounts.set(key, (edgeCounts.get(key) || 0) + 1);
  }
  const edgeIndexes = new Map<string, number>();
  return (source: string, target: string) => {
    const key = source;
    const index = edgeIndexes.get(key) || 0;
    edgeIndexes.set(key, index + 1);
    const count = edgeCounts.get(key) || 1;
    const sourceY = positions.get(source)?.y || 0;
    const targetY = positions.get(target)?.y || 0;
    const naturalSign = targetY >= sourceY ? 1 : -1;
    return (index - (count - 1) / 2) * naturalSign;
  };
}

function allGraphEdges(definition: WorkflowDefinition): WorkflowEdge[] {
  const conditionalEdges = (definition.conditionalEdges || []).flatMap((conditionalEdge) =>
    conditionalEdge.routes.map((route) => ({
      source: conditionalEdge.source,
      target: route.target,
    }))
  );
  return [...(definition.edges || []), ...conditionalEdges];
}

function layoutPositions(definition: WorkflowDefinition): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({
    rankdir: "LR",
    nodesep: 70,
    ranksep: 120,
    marginx: 40,
    marginy: 40,
  });
  for (const node of definition.nodes) {
    graph.setNode(node.id, { width: FLOW_NODE_WIDTH, height: FLOW_NODE_HEIGHT });
  }
  for (const edge of allGraphEdges(definition)) {
    graph.setEdge(edge.source, edge.target);
  }
  dagre.layout(graph);
  for (const node of definition.nodes) {
    const position = graph.node(node.id);
    positions.set(node.id, {
      x: (position?.x || 0) - FLOW_NODE_WIDTH / 2,
      y: (position?.y || 0) - FLOW_NODE_HEIGHT / 2,
    });
  }
  return positions;
}

function nextNodeId(nodes: WorkflowNode[]): string {
  let index = nodes.length + 1;
  const existing = new Set(nodes.map((node) => node.id));
  while (existing.has(`node_${index}`)) index += 1;
  return `node_${index}`;
}

function removeEdgeById(definition: WorkflowDefinition, edgeId: string): WorkflowDefinition {
  const conditionSeparator = edgeId.indexOf(":");
  const sourceTarget = conditionSeparator >= 0 ? edgeId.slice(0, conditionSeparator) : edgeId;
  const condition = conditionSeparator >= 0 ? edgeId.slice(conditionSeparator + 1) : "";
  const [source, target] = sourceTarget.split("->");
  if (!source || !target) return definition;
  const conditionalEdges = (definition.conditionalEdges || [])
    .map((conditionalEdge) => conditionalEdge.source !== source
      ? conditionalEdge
      : {
          ...conditionalEdge,
          routes: conditionalEdge.routes.filter((route) => !(route.target === target && (!condition || route.condition === condition))),
        })
    .filter((conditionalEdge) => conditionalEdge.routes.length > 0);
  const conditionalSources = new Set(conditionalEdges.map((conditionalEdge) => conditionalEdge.source));
  return {
    ...definition,
    edges: definition.edges.filter((edge) => !(edge.source === source && edge.target === target)),
    nodes: definition.nodes.map((node) =>
      node.id === source && !conditionalSources.has(source) ? { ...node, routingFunction: undefined } : node
    ),
    conditionalEdges,
  };
}

function nextRouteCondition(routes: { condition: string }[]): string {
  const existing = new Set(routes.map((route) => route.condition));
  let index = routes.length + 1;
  while (existing.has(`condition_${index}`)) index += 1;
  return `condition_${index}`;
}

function addOutgoingEdge(definition: WorkflowDefinition, source: string, target: string): {
  definition: WorkflowDefinition;
  edgeId: string;
  message: string;
} {
  const normalOutgoing = definition.edges.filter((edge) => edge.source === source);
  const otherNormalEdges = definition.edges.filter((edge) => edge.source !== source);
  const conditionalEdges = definition.conditionalEdges || [];
  const existingConditional = conditionalEdges.find((edge) => edge.source === source);
  if (!existingConditional && normalOutgoing.length === 0) {
    return {
      definition: { ...definition, edges: [...definition.edges, { source, target }] },
      edgeId: `${source}->${target}`,
      message: "Connection added",
    };
  }

  const routes = [...(existingConditional?.routes || [])];
  for (const edge of normalOutgoing) {
    routes.push({ condition: nextRouteCondition(routes), target: edge.target });
  }
  const condition = nextRouteCondition(routes);
  routes.push({ condition, target });
  const nextNodes = definition.nodes.map((node) =>
    node.id === source && !node.routingFunction
      ? { ...node, routingFunction: defaultRoutingFunction(source, routes) }
      : node
  );
  return {
    definition: {
      ...definition,
      nodes: nextNodes,
      edges: otherNormalEdges,
      conditionalEdges: [
        ...conditionalEdges.filter((edge) => edge.source !== source),
        { source, routes },
      ],
    },
    edgeId: `${source}->${target}:${condition}`,
    message: "Outputs converted to conditional routes",
  };
}

function WorkflowAgentNode({ data }: NodeProps<Node<WorkflowNodeData>>) {
  const node = data.workflowNode;
  const isControl = node.type === "start" || node.type === "end";
  const Icon = node.type === "tool" ? Wrench : node.type === "end" ? Square : CircleDot;
  return (
    <div className="w-[190px] border bg-card shadow-sm">
      {!isControl || node.type === "end" ? <Handle type="target" position={Position.Left} className="!bg-muted-foreground" /> : null}
      {!isControl || node.type === "start" ? <Handle type="source" position={Position.Right} className="!bg-primary" /> : null}
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <div className={cn("flex h-7 w-7 items-center justify-center text-[10px] font-bold uppercase text-white", data.color)}>
          {node.type === "agent" ? data.label.slice(0, 2) : <Icon className="h-4 w-4" />}
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{data.label}</div>
          <div className="truncate text-[11px] text-muted-foreground">
            {node.type === "agent" ? `@${node.agentId}` : node.type}
          </div>
        </div>
      </div>
      <div className="flex flex-wrap gap-1 px-3 py-2">
        {data.isEntry && <Badge className="h-5 text-[10px]">Entry</Badge>}
        {data.isOutput && <Badge variant="outline" className="h-5 text-[10px]">Output</Badge>}
        {!data.isEntry && !data.isOutput && <span className="text-[11px] text-muted-foreground">Agent node</span>}
      </div>
    </div>
  );
}

function WorkflowGraphEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  markerEnd,
  style,
  data,
  label,
  selected,
}: EdgeProps<Edge<WorkflowEdgeData>>) {
  const lane = data?.lane || 0;
  const laneOffset = lane * EDGE_LANE_GAP;
  const isBackEdge = data?.backEdge || false;
  const distance = Math.max(Math.abs(targetX - sourceX), 120);
  const controlDistance = Math.max(distance * 0.45, 90);
  const loopOffset = (sourceY <= targetY ? -1 : 1) * (110 + Math.abs(laneOffset));
  const yOffset = isBackEdge ? loopOffset : laneOffset;
  const controlSourceX = isBackEdge ? sourceX + 90 : sourceX + controlDistance;
  const controlTargetX = isBackEdge ? targetX - 90 : targetX - controlDistance;
  const controlSourceY = sourceY + yOffset;
  const controlTargetY = targetY + yOffset;
  const edgePath = `M ${sourceX},${sourceY} C ${controlSourceX},${controlSourceY} ${controlTargetX},${controlTargetY} ${targetX},${targetY}`;
  const labelX = (sourceX + targetX + controlSourceX + controlTargetX) / 4;
  const labelY = (sourceY + targetY + controlSourceY + controlTargetY) / 4;

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          strokeWidth: selected ? 2.5 : 1.6,
        }}
      />
      {label ? (
        <EdgeLabelRenderer>
          <div
            className="nodrag nopan border bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground shadow-sm"
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: "all",
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}

const nodeTypes: NodeTypes = {
  workflowAgent: WorkflowAgentNode,
};

const edgeTypes: EdgeTypes = {
  workflow: WorkflowGraphEdge,
};

export function WorkflowEditor({
  enabled,
  workflowId,
  workflowName,
  definitionJson,
  agents,
  teamAgentIds,
  leaderAgentId,
  onEnabledChange,
  onWorkflowIdChange,
  onWorkflowNameChange,
  onDefinitionJsonChange,
  onValidateDefinition,
}: WorkflowEditorProps) {
  const fallbackAgentId = leaderAgentId || teamAgentIds[0] || "";
  const [mode, setMode] = useState<EditorMode>("graph");
  const [definition, setDefinition] = useState<WorkflowDefinition>(() => parseDefinitionJson(definitionJson, fallbackAgentId));
  const [nodes, setNodes] = useState<Node<WorkflowNodeData>[]>(() => definitionToFlow(definition, agents).nodes);
  const [edges, setEdges] = useState<Edge<WorkflowEdgeData>[]>(() => definitionToFlow(definition, agents).edges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(definition.nodes[0]?.id || null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [jsonDraft, setJsonDraft] = useState(definitionJson || prettyJson(definition));
  const [status, setStatus] = useState("");

  useEffect(() => {
    if (!enabled) return;
    try {
      const parsed = parseDefinitionJson(definitionJson, fallbackAgentId);
      /* eslint-disable react-hooks/set-state-in-effect */
      setDefinition(parsed);
      const flow = definitionToFlow(parsed, agents);
      setNodes(flow.nodes);
      setEdges(flow.edges);
      setJsonDraft(prettyJson(parsed));
      setSelectedNodeId((current) => current && parsed.nodes.some((node) => node.id === current) ? current : parsed.nodes[0]?.id || null);
      /* eslint-enable react-hooks/set-state-in-effect */
    } catch {
      setJsonDraft(definitionJson);
    }
  }, [agents, definitionJson, enabled, fallbackAgentId]);

  const commitDefinition = useCallback((nextDefinition: WorkflowDefinition, message = "") => {
    const normalized = normalizeDefinition(nextDefinition);
    setDefinition(normalized);
    const flow = definitionToFlow(normalized, agents);
    setNodes(flow.nodes);
    setEdges(flow.edges);
    const json = prettyJson(normalized);
    setJsonDraft(json);
    onDefinitionJsonChange(json);
    if (message) setStatus(message);
  }, [agents, onDefinitionJsonChange]);

  const handleEnabledChange = (nextEnabled: boolean) => {
    onEnabledChange(nextEnabled);
    if (nextEnabled && !definitionJson.trim()) {
      const initial = defaultDefinition(fallbackAgentId);
      commitDefinition(initial);
    }
  };

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((current) => applyNodeChanges(changes, current) as Node<WorkflowNodeData>[]);
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((current) => applyEdgeChanges(changes, current));
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target || connection.source === connection.target) {
      setStatus("Invalid connection");
      return;
    }
    if (allGraphEdges(definition).some((edge) => edge.source === connection.source && edge.target === connection.target)) {
      setStatus("Connection already exists");
      return;
    }
    const result = addOutgoingEdge(definition, connection.source, connection.target);
    commitDefinition(result.definition, result.message);
    setSelectedNodeId(null);
    setSelectedEdgeId(result.edgeId);
  }, [commitDefinition, definition]);

  const addAgentNode = () => {
    const agentId = teamAgentIds.find(Boolean) || fallbackAgentId;
    if (!agentId) {
      setStatus("Select at least one team member first");
      return;
    }
    const nodeId = nextNodeId(definition.nodes);
    const nextNodes = [
      ...definition.nodes,
      { id: nodeId, type: "agent", agentId, prompt: "", inputTemplate: "" },
    ];
    commitDefinition({
      ...definition,
      entrypoint: definition.entrypoint || nodeId,
      outputNode: definition.outputNode || nodeId,
      nodes: nextNodes,
    }, "Agent node added");
    setSelectedNodeId(nodeId);
  };

  const addToolNode = () => {
    const nodeId = nextNodeId(definition.nodes);
    const nextNodes = [
      ...definition.nodes,
      { id: nodeId, type: "tool", prompt: "Describe the tool call or tool result.", inputTemplate: "" },
    ];
    commitDefinition({ ...definition, nodes: nextNodes }, "Tool node added");
    setSelectedNodeId(nodeId);
    setSelectedEdgeId(null);
  };

  const updateWorkflowNode = (nodeId: string, patch: Partial<WorkflowNode>) => {
    commitDefinition({
      ...definition,
      nodes: definition.nodes.map((node) => node.id === nodeId ? { ...node, ...patch } : node),
    });
  };

  const renameNode = (nodeId: string, nextId: string) => {
    if (!nextId || nextId === nodeId) return;
    if (!/^[a-zA-Z0-9_-]+$/.test(nextId)) {
      setStatus("Node ID can only contain letters, numbers, _ and -");
      return;
    }
    if (definition.nodes.some((node) => node.id === nextId)) {
      setStatus("Node ID already exists");
      return;
    }
    commitDefinition({
      ...definition,
      entrypoint: definition.entrypoint === nodeId ? nextId : definition.entrypoint,
      outputNode: definition.outputNode === nodeId ? nextId : definition.outputNode,
      nodes: definition.nodes.map((node) => node.id === nodeId ? { ...node, id: nextId } : node),
      edges: definition.edges.map((edge) => ({
        ...edge,
        source: edge.source === nodeId ? nextId : edge.source,
        target: edge.target === nodeId ? nextId : edge.target,
      })),
      conditionalEdges: (definition.conditionalEdges || []).map((conditionalEdge) => ({
        ...conditionalEdge,
        source: conditionalEdge.source === nodeId ? nextId : conditionalEdge.source,
        routes: conditionalEdge.routes.map((route) => ({
          ...route,
          target: route.target === nodeId ? nextId : route.target,
        })),
      })),
    });
    setSelectedNodeId(nextId);
  };

  const deleteSelectedNode = () => {
    if (!selectedNodeId) return;
    const nextNodes = definition.nodes.filter((node) => node.id !== selectedNodeId);
    const nextEdges = definition.edges.filter((edge) => edge.source !== selectedNodeId && edge.target !== selectedNodeId);
    commitDefinition({
      ...definition,
      nodes: nextNodes,
      edges: nextEdges,
      conditionalEdges: (definition.conditionalEdges || [])
        .filter((conditionalEdge) => conditionalEdge.source !== selectedNodeId)
        .map((conditionalEdge) => ({
          ...conditionalEdge,
          routes: conditionalEdge.routes.filter((route) => route.target !== selectedNodeId),
        }))
        .filter((conditionalEdge) => conditionalEdge.routes.length > 0),
      entrypoint: definition.entrypoint === selectedNodeId ? nextNodes[0]?.id || "" : definition.entrypoint,
      outputNode: definition.outputNode === selectedNodeId ? nextNodes[nextNodes.length - 1]?.id || "" : definition.outputNode,
    }, "Node deleted");
    setSelectedNodeId(nextNodes[0]?.id || null);
  };

  const deleteSelectedEdges = (deletedEdges: Edge[]) => {
    if (!deletedEdges.length) return;
    const nextDefinition = deletedEdges.reduce(
      (current, edge) => removeEdgeById(current, edge.id),
      definition,
    );
    commitDefinition(nextDefinition, "Connection removed");
    if (selectedEdgeId && deletedEdges.some((edge) => edge.id === selectedEdgeId)) {
      setSelectedEdgeId(null);
    }
  };

  const autoLayout = () => {
    const flow = definitionToFlow(definition, agents);
    setNodes(flow.nodes);
    setEdges(flow.edges);
    setStatus("Layout reset");
  };

  const applyJson = () => {
    try {
      const parsed = parseDefinition(JSON.parse(jsonDraft));
      commitDefinition(parsed, "JSON applied");
    } catch (err) {
      setStatus((err as Error).message);
    }
  };

  const formatJson = () => {
    try {
      const parsed = parseDefinition(JSON.parse(jsonDraft));
      const formatted = prettyJson(parsed);
      setJsonDraft(formatted);
      onDefinitionJsonChange(formatted);
      setStatus("JSON formatted");
    } catch (err) {
      setStatus((err as Error).message);
    }
  };

  const importJsonFile = async (file: File | undefined) => {
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = parseDefinition(JSON.parse(text));
      commitDefinition(parsed, `Imported ${file.name}`);
    } catch (err) {
      setStatus((err as Error).message);
    }
  };

  const validateWorkflow = async () => {
    setStatus("Validating workflow...");
    try {
      await onValidateDefinition(definition);
      setStatus(`Workflow is valid: ${definition.nodes.length} nodes, ${allGraphEdges(definition).length} edges`);
    } catch (err) {
      setStatus((err as Error).message);
    }
  };

  const selectedNode = useMemo(
    () => selectedEdgeId ? null : definition.nodes.find((node) => node.id === selectedNodeId) || null,
    [definition.nodes, selectedEdgeId, selectedNodeId],
  );
  const selectedNodeConditionalEdge = useMemo(
    () => selectedNode ? (definition.conditionalEdges || []).find((edge) => edge.source === selectedNode.id) || null : null,
    [definition.conditionalEdges, selectedNode],
  );
  const selectedEdge = useMemo(
    () => edges.find((edge) => edge.id === selectedEdgeId) || null,
    [edges, selectedEdgeId],
  );

  const updateSelectedEdgeCondition = (condition: string) => {
    if (!selectedEdge) return;
    const source = selectedEdge.source;
    const target = selectedEdge.target;
    let nextDefinition = removeEdgeById(definition, selectedEdge.id);
    if (condition.trim()) {
      const existingConditional = nextDefinition.conditionalEdges || [];
      const existingForSource = existingConditional.find((edge) => edge.source === source);
      const nextConditionalEdges = existingForSource
        ? existingConditional.map((edge) => edge.source === source
            ? {
                ...edge,
                routes: [...edge.routes, { condition: condition.trim(), target }],
              }
            : edge)
        : [...existingConditional, { source, routes: [{ condition: condition.trim(), target }] }];
      nextDefinition = {
        ...nextDefinition,
        nodes: nextDefinition.nodes.map((node) =>
          node.id === source && !node.routingFunction
            ? {
                ...node,
                routingFunction: defaultRoutingFunction(
                  source,
                  nextConditionalEdges.find((edge) => edge.source === source)?.routes || [],
                ),
              }
            : node
        ),
        conditionalEdges: nextConditionalEdges,
      };
      commitDefinition(nextDefinition, "Condition updated");
      setSelectedEdgeId(`${source}->${target}:${condition.trim()}`);
    } else {
      nextDefinition = { ...nextDefinition, edges: [...nextDefinition.edges, { source, target }] };
      commitDefinition(nextDefinition, "Condition removed");
      setSelectedEdgeId(`${source}->${target}`);
    }
  };

  return (
    <div className="space-y-3 border-t pt-4">
      <div className="flex items-center justify-between gap-4">
        <label className="text-xs font-medium text-muted-foreground">Workflow</label>
        <Switch checked={enabled} onCheckedChange={handleEnabledChange} disabled={teamAgentIds.length === 0} />
      </div>

      {enabled && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Workflow ID</label>
              <Input
                value={workflowId}
                onChange={(event) => onWorkflowIdChange(event.target.value)}
                placeholder="e.g. delivery-flow"
                className="font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Workflow Name</label>
              <Input
                value={workflowName}
                onChange={(event) => onWorkflowNameChange(event.target.value)}
                placeholder="e.g. Delivery Flow"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex border">
              <Button type="button" variant={mode === "graph" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("graph")}>
                <GitBranch className="h-3.5 w-3.5" />
                Graph
              </Button>
              <Button type="button" variant={mode === "json" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("json")}>
                <FileJson className="h-3.5 w-3.5" />
                JSON
              </Button>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={addAgentNode}>
              <Plus className="h-3.5 w-3.5" />
              Add Agent
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={addToolNode}>
              <Wrench className="h-3.5 w-3.5" />
              Add Tool
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={autoLayout}>
              <LayoutDashboard className="h-3.5 w-3.5" />
              Layout
            </Button>
            <label className="inline-flex">
              <input
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(event) => importJsonFile(event.target.files?.[0])}
              />
              <Button type="button" variant="outline" size="sm" asChild>
                <span>
                  <Upload className="h-3.5 w-3.5" />
                  Import
                </span>
              </Button>
            </label>
            <Button type="button" variant="outline" size="sm" onClick={validateWorkflow}>
              <Check className="h-3.5 w-3.5" />
              Validate
            </Button>
            {status && <span className="text-xs text-muted-foreground">{status}</span>}
          </div>

          {mode === "graph" ? (
            <div className="grid min-h-[520px] grid-cols-1 border lg:grid-cols-[minmax(0,1fr)_320px]">
              <div className="h-[520px] border-b lg:border-b-0 lg:border-r">
                <ReactFlowProvider>
                  <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    nodeTypes={nodeTypes}
                    edgeTypes={edgeTypes}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onEdgesDelete={deleteSelectedEdges}
                    onConnect={onConnect}
                    onNodeClick={(_event, node) => {
                      setSelectedEdgeId(null);
                      setSelectedNodeId(node.id);
                    }}
                    onEdgeClick={(_event, edge) => {
                      setSelectedNodeId(null);
                      setSelectedEdgeId(edge.id);
                    }}
                    fitView
                    fitViewOptions={{ padding: 0.25 }}
                    proOptions={{ hideAttribution: true }}
                  >
                    <Background />
                    <Controls />
                  </ReactFlow>
                </ReactFlowProvider>
              </div>

              <div className="space-y-3 p-4">
                {selectedEdge ? (
                  <>
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <div className="text-sm font-medium">Edge</div>
                        <div className="text-xs text-muted-foreground">
                          {selectedEdge.source} {"->"} {selectedEdge.target}
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          commitDefinition(removeEdgeById(definition, selectedEdge.id), "Connection removed");
                          setSelectedEdgeId(null);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">Condition</label>
                      <Input
                        value={selectedEdge.data?.condition || ""}
                        onChange={(event) => updateSelectedEdgeCondition(event.target.value)}
                        placeholder="e.g. approved"
                        className="font-mono"
                      />
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Empty condition stores this as a normal edge. Any condition stores it in conditionalEdges.
                    </div>
                  </>
                ) : selectedNode ? (
                  <>
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <div className="text-sm font-medium">Node</div>
                        <div className="text-xs text-muted-foreground">
                          {(selectedNode.type || "agent") === "agent" ? `@${selectedNode.agentId || ""}` : selectedNode.type}
                        </div>
                      </div>
                      <Button type="button" variant="ghost" size="icon" onClick={deleteSelectedNode}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">Node ID</label>
                      <Input value={selectedNode.id} onChange={(event) => renameNode(selectedNode.id, event.target.value)} className="font-mono" />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">Type</label>
                      <Select
                        value={selectedNode.type || "agent"}
                        onValueChange={(type) => updateWorkflowNode(selectedNode.id, {
                          type,
                          agentId: type === "agent" ? selectedNode.agentId || teamAgentIds[0] || "" : "",
                        })}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="start">Start</SelectItem>
                          <SelectItem value="agent">Agent</SelectItem>
                          <SelectItem value="tool">Tool</SelectItem>
                          <SelectItem value="end">End</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    {(selectedNode.type || "agent") === "agent" && (
                      <div className="space-y-1.5">
                        <label className="text-xs font-medium text-muted-foreground">Agent</label>
                        <Select value={selectedNode.agentId || ""} onValueChange={(agentId) => updateWorkflowNode(selectedNode.id, { agentId })}>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {teamAgentIds.map((agentId) => (
                              <SelectItem key={agentId} value={agentId}>
                                {agents[agentId]?.name || agentId}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">Prompt</label>
                      <Textarea
                        value={selectedNode.prompt || ""}
                        onChange={(event) => updateWorkflowNode(selectedNode.id, { prompt: event.target.value })}
                        className="min-h-24 text-sm"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">Input Template</label>
                      <Textarea
                        value={selectedNode.inputTemplate || ""}
                        onChange={(event) => updateWorkflowNode(selectedNode.id, { inputTemplate: event.target.value })}
                        className="min-h-24 font-mono text-xs"
                      />
                    </div>
                    {selectedNodeConditionalEdge && (
                      <div className="space-y-2 border-t pt-3">
                        <div>
                          <div className="text-xs font-medium text-muted-foreground">Routing Function</div>
                          <div className="text-[11px] text-muted-foreground">
                            Return one of: {selectedNodeConditionalEdge.routes.map((route) => route.condition).join(", ")}
                          </div>
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium text-muted-foreground">Language</label>
                          <Input value="python" disabled className="font-mono" />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium text-muted-foreground">Entrypoint</label>
                          <Input
                            value={selectedNode.routingFunction?.entrypoint || "route"}
                            onChange={(event) => updateWorkflowNode(selectedNode.id, {
                              routingFunction: {
                                ...(selectedNode.routingFunction || defaultRoutingFunction(selectedNode.id, selectedNodeConditionalEdge.routes)),
                                language: "python",
                                entrypoint: event.target.value,
                              },
                            })}
                            className="font-mono"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium text-muted-foreground">Python Code</label>
                          <Textarea
                            value={(selectedNode.routingFunction || defaultRoutingFunction(selectedNode.id, selectedNodeConditionalEdge.routes)).code}
                            onChange={(event) => updateWorkflowNode(selectedNode.id, {
                              routingFunction: {
                                ...(selectedNode.routingFunction || defaultRoutingFunction(selectedNode.id, selectedNodeConditionalEdge.routes)),
                                language: "python",
                                code: event.target.value,
                              },
                            })}
                            className="min-h-44 font-mono text-xs"
                            spellCheck={false}
                          />
                        </div>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" variant={definition.entrypoint === selectedNode.id ? "default" : "outline"} size="sm" onClick={() => commitDefinition({ ...definition, entrypoint: selectedNode.id })}>
                        Entry
                      </Button>
                      <Button type="button" variant={definition.outputNode === selectedNode.id ? "default" : "outline"} size="sm" onClick={() => commitDefinition({ ...definition, outputNode: selectedNode.id })}>
                        Output
                      </Button>
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-muted-foreground">Select or add a node.</div>
                )}
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <Textarea
                value={jsonDraft}
                onChange={(event) => setJsonDraft(event.target.value)}
                className="min-h-[520px] font-mono text-xs leading-relaxed"
                spellCheck={false}
              />
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" size="sm" onClick={applyJson}>
                  <Check className="h-3.5 w-3.5" />
                  Apply JSON
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={formatJson}>
                  <Wand2 className="h-3.5 w-3.5" />
                  Format
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
