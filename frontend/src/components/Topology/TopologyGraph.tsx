import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { TopologyNode, TopologyEdge } from '../../store/topology'

interface Props {
  nodes: TopologyNode[]
  edges: TopologyEdge[]
}

const NODE_COLORS: Record<string, string> = {
  gateway: '#1976d2',
  switch: '#f57c00',
  power: '#7b1fa2',
  sensor: '#388e3c',
}

const WIDTH = 800
const HEIGHT = 500

interface SimNode extends d3.SimulationNodeDatum {
  id: string
  name: string
  device_type: string
  status: string
  has_active_alarm: boolean
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  id: string
  dependency_type: string
  is_propagating?: boolean
}

export default function TopologyGraph({ nodes, edges }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const simNodes: SimNode[] = nodes.map((n) => ({
      id: n.device_id,
      name: n.name,
      device_type: n.device_type,
      status: n.status,
      has_active_alarm: n.has_active_alarm,
    }))

    const nodeMap = new Map(simNodes.map((n) => [n.id, n]))

    const simLinks: SimLink[] = edges
      .filter((e) => nodeMap.has(e.parent_device_id) && nodeMap.has(e.child_device_id))
      .map((e) => ({
        source: e.parent_device_id,
        target: e.child_device_id,
        id: e.id,
        dependency_type: e.dependency_type,
        is_propagating: e.is_propagating,
      }))

    const defs = svg.append('defs')

    defs.append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 28)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#999')

    defs.append('marker')
      .attr('id', 'arrow-red')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 28)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#f44336')

    const simulation = d3.forceSimulation(simNodes)
      .force('link', d3.forceLink<SimNode, SimLink>(simLinks).id((d) => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(WIDTH / 2, HEIGHT / 2))
      .force('y', d3.forceY(HEIGHT / 2).strength(0.05))

    const link = svg.append('g')
      .selectAll('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', (d) => d.is_propagating ? '#f44336' : '#999')
      .attr('stroke-width', (d) => d.is_propagating ? 3 : 1.5)
      .attr('stroke-dasharray', (d) => d.is_propagating ? '8,4' : 'none')
      .attr('marker-end', (d) => d.is_propagating ? 'url(#arrow-red)' : 'url(#arrow)')
      .classed('propagating', (d) => !!d.is_propagating)

    const node = svg.append('g')
      .selectAll('g')
      .data(simNodes)
      .join('g')
      .call(d3.drag<SVGGElement, SimNode>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
      )

    node.append('circle')
      .attr('r', 18)
      .attr('fill', (d) => NODE_COLORS[d.device_type] || '#666')
      .attr('stroke', (d) => d.has_active_alarm ? '#f44336' : '#fff')
      .attr('stroke-width', (d) => d.has_active_alarm ? 3 : 2)

    node.append('text')
      .attr('dy', 32)
      .attr('text-anchor', 'middle')
      .attr('font-size', '11px')
      .attr('fill', '#333')
      .text((d) => d.name)

    node.append('text')
      .attr('dy', 4)
      .attr('text-anchor', 'middle')
      .attr('font-size', '9px')
      .attr('fill', '#fff')
      .attr('font-weight', 'bold')
      .text((d) => d.device_type.charAt(0).toUpperCase())

    node.append('title')
      .text((d) => `${d.name}\nType: ${d.device_type}\nStatus: ${d.status}`)

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)

      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
    })

    return () => {
      simulation.stop()
    }
  }, [nodes, edges])

  return (
    <>
      <style>{`
        @keyframes dash-flow {
          to { stroke-dashoffset: -24; }
        }
        .propagating {
          animation: dash-flow 0.6s linear infinite;
        }
      `}</style>
      <svg
        ref={svgRef}
        width={WIDTH}
        height={HEIGHT}
        style={{ display: 'block' }}
      />
    </>
  )
}
