from liblathe.boundbox import BoundBox
from liblathe.command import Command
from liblathe.point import Point
from liblathe.segment import Segment


class SegmentGroup:
    """Container Group for segments"""

    def __init__(self):
        self.segments = []

    def add_segment(self, segment):
        """Add segment to group"""

        self.segments.append(segment)

    def get_segments(self):
        """Return segments of group as a list"""

        return self.segments

    def extend(self, segmentgroup):
        """Add segment group to this segmentgroup"""

        self.segments.extend(segmentgroup.get_segments())

    def count(self):
        """Return the number of segments in the segmentgroup"""

        return len(self.segments)

    def boundbox(self):
        """Return the boundbox for the segmentgroup"""

        xvalues = []
        yvalues = []
        zvalues = []

        # collect all points from each segment by direction
        for segment in self.get_segments():
            xvalues.extend(segment.get_all_axis_positions('X'))
            yvalues.extend(segment.get_all_axis_positions('Y'))
            zvalues.extend(segment.get_all_axis_positions('Z'))

        XMin = min(xvalues, key=abs)
        XMax = max(xvalues, key=abs)
        YMin = min(yvalues, key=abs)
        YMax = max(yvalues, key=abs)
        ZMin = min(zvalues, key=abs)
        ZMax = max(zvalues, key=abs)

        pt1 = Point(XMin, YMin, ZMin)
        pt2 = Point(XMax, YMax, ZMax)

        segmentgroupBoundBox = BoundBox(pt1, pt2)

        return segmentgroupBoundBox

    def join_segments(self):
        """join segments of the segmentgroup"""

        segments = self.get_segments()
        segmentgroupOut = SegmentGroup()

        for i in range(len(segments)):

            pt1 = segments[i].start
            pt2 = segments[i].end

            if i != 0:
                seg1 = segments[i - 1]
                intersect, pt = seg1.intersect(segments[i], extend=True)
                if intersect:
                    if type(pt) is list:
                        pt = pt1.nearest(pt)
                    pt1 = pt

            if i != len(segments) - 1:
                seg2 = segments[i + 1]
                intersect2, pt = seg2.intersect(segments[i], extend=True)
                if intersect2:
                    # print('intersect2')
                    if type(pt) is list:
                        # print('join_segments type of', type(pt))
                        pt = pt2.nearest(pt)
                    pt2 = pt

                    # print('join_segments', i, pt1, pt2, pt2.X, pt2.Z)

            if pt1 and pt2:
                if segments[i].bulge != 0:
                    nseg = Segment(pt1, pt2)
                    rad = segments[i].get_centre_point().distance_to(pt1)
                    if segments[i].bulge < 0:
                        rad = 0 - rad
                    nseg.set_bulge_from_radius(rad)
                    segmentgroupOut.add_segment(nseg)
                else:
                    segmentgroupOut.add_segment(Segment(pt1, pt2))
            else:
                # No Intersections found. Return the segment in its current state
                # print('join_segments - No Intersection found for index:', i)
                segmentgroupOut.add_segment(segments[i])

        self.segments = segmentgroupOut.get_segments()

    def previous_segment_connected(self, segment):
        """returns bool if segment is connect to the previous segment"""

        currentIdx = self.segments.index(segment)
        previousIdx = currentIdx - 1

        if not currentIdx == 0:
            currentStartPt = segment.start
            previousEndPt = self.segments[previousIdx].end

            if currentStartPt.is_same(previousEndPt):
                return True

        return False

    def get_min_retract_x(self, segment, part_segment_group):
        """ returns the minimum x retract based on the current segments and the part_segments """

        part_segments = part_segment_group.get_segments()
        currentIdx = self.segments.index(segment)
        x_values = []

        # get the xmax from the current pass segments
        for idx, seg in enumerate(self.segments):
            x_values.append(seg.get_extent_max('X'))
            if idx == currentIdx:
                break

        # get the xmax from the part segments up to the z position of the current segment
        seg_z_max = segment.get_extent_max('Z')
        for part_seg in part_segments:

            part_seg_z_max = part_seg.get_extent_max('Z')
            x_values.append(part_seg.get_extent_max('X'))

            if part_seg_z_max < seg_z_max:
                break

        min_retract_x = max(x_values, key=abs)
        return min_retract_x

    def to_commands(self, part_segment_group, stock, step_over, hSpeed, vSpeed):
        """converts segmentgroup to gcode commands"""

        segments = self.get_segments()

        cmds = []
        # TODO: Move the G18 to a PATH Class? it doent need to be added to every segment group
        cmd = Command('G18')  # xz plane
        cmds.append(cmd)

        for seg in segments:
            min_x_retract = self.get_min_retract_x(seg, part_segment_group)
            x_retract = min_x_retract - step_over
            min_z_retract = stock.ZMax
            z_retract = min_z_retract + step_over

            # print('min_x_retract:', min_x_retract)

            if segments.index(seg) == 0:
                # params = {'X': seg.start.X, 'Y': 0, 'Z': seg.start.Z + step_over, 'F': hSpeed}
                params = {'X': seg.start.X, 'Y': 0, 'Z': z_retract, 'F': hSpeed}
                rapid = Command('G0', params)
                cmds.append(rapid)

                params = {'X': seg.start.X, 'Y': 0, 'Z': seg.start.Z, 'F': hSpeed}
                rapid = Command('G0', params)
                cmds.append(rapid)

            if seg.bulge == 0:
                if not self.previous_segment_connected(seg):
                    # if edges.index(edge) == 1:
                    pt = seg.start  # edge.valueAt(edge.FirstParameter)
                    params = {'X': pt.X, 'Y': pt.Y, 'Z': pt.Z, 'F': hSpeed}
                    cmd = Command('G0', params)
                    cmds.append(cmd)

                pt = seg.end  # edge.valueAt(edge.LastParameter)
                params = {'X': pt.X, 'Y': pt.Y, 'Z': pt.Z, 'F': hSpeed}
                cmd = Command('G1', params)

            if seg.bulge != 0:
                # TODO: define arctype from bulge sign +/-

                pt1 = seg.start
                pt2 = seg.end
                # print('toPathCommand - bulge', seg.bulge )
                if seg.bulge < 0:
                    arcType = 'G2'
                else:
                    arcType = 'G3'

                cen = seg.get_centre_point().sub(pt1)
                # print('toPathCommand arc cen', seg.get_centre_point().X, seg.get_centre_point().Z)
                params = {'X': pt2.X, 'Z': pt2.Z, 'I': cen.X, 'K': cen.Z, 'F': hSpeed}
                # print('toPathCommand', params)
                cmd = Command(arcType, params)

            cmds.append(cmd)

            if segments.index(seg) == len(segments) - 1:
                params = {'X': x_retract, 'Y': 0, 'Z': seg.end.Z, 'F': hSpeed}
                rapid = Command('G0', params)
                cmds.append(rapid)

                # params = {'X': x_retract, 'Y': 0, 'Z': segments[0].start.Z + step_over, 'F': hSpeed}
                params = {'X': x_retract, 'Y': 0, 'Z': z_retract, 'F': hSpeed}

                rapid = Command('G0', params)
                cmds.append(rapid)

        return cmds