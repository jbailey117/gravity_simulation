from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QGraphicsScene,
    QOpenGLWidget,
    QGraphicsView,
    QGraphicsPixmapItem
)
from PyQt5.QtCore import (
    Qt,
    QTimer,
    QSize,
    QPointF,
    QProcess
)
from PyQt5.QtGui import (
    QPainter,
    QPixmap,
    QRadialGradient,
    QCursor,
    QColor
)
import numpy as np
from random import randint
from math import pi
import sys

t_step = 1
dt = t_step/200
planets = 5

class MainWindow(QMainWindow):
    def __init__(self, size:QSize):
        super().__init__()
        self.setWindowTitle("Demo")
        self.scene = QGraphicsScene()
        self.map = self.Game(self.scene, size)
        QCursor.setPos(int(size.width()/2), int(size.height()/2))
        self.setCursor(Qt.BlankCursor)
        self.map.setMouseTracking(True)
        self.setCentralWidget(self.map)
        self.showFullScreen()

    class Game(QGraphicsView):
        def __init__(self, scene:QGraphicsScene, size:QSize):
            super().__init__()
            self.scene = scene
            self.setScene(self.scene)
            self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
            self.setViewport(QOpenGLWidget())

            self.setViewportMargins(0, 0, 0, 0)
            self.setMinimumSize(QSize(1600, 1200))
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

            self.pixmap = QPixmap(size.width(), size.height())
            self.pixmap.fill(Qt.black)

            self.view = QGraphicsPixmapItem(self.pixmap)
            self.view.setPos(0, 0)
            self.scene.addItem(self.view)
            self.planets = [self.Planet(self) for _ in range(0, planets)]
            for planet in self.planets:
                planet.acc = planet.get_acceleration()
            self.start()

            self.light = np.array([0, 0, 0], dtype=float)
            self.camera = self.Camera(self, 10)
            self.l_corner = np.array([0, 0], dtype=float)
            
            self.cm = np.array([0, 0, 0], dtype=float)

        def keyPressEvent(self, event):
            if event.key() == Qt.Key_Escape:
                app.exit()
            self.camera.keyEvent(event, True)
            return super().keyPressEvent(event)
            
        def keyReleaseEvent(self, event):
            self.camera.keyEvent(event, False)
            return super().keyReleaseEvent(event)
        
        def mouseMoveEvent(self, event):
            self.camera.mouseMoveEvent(event)
            return super().mouseMoveEvent(event)

        def start(self):
            global t_step
            self.timer = QTimer()
            self.timer.timeout.connect(self.update)
            self.timer.start(t_step)

        def update(self):
            self.camera.update()
            #self.light = self.camera.pos
            self.planets = sorted(self.planets, key=lambda x: self.camera.get_dist(x.pos), reverse=True)
            self.pixmap.fill(Qt.black)
            painter = QPainter(self.pixmap)
            accelerations = np.array([planet.get_acceleration() for planet in self.planets])
            cm = np.array([0, 0, 0], dtype=float)
            m_tot = 0
            for i in range(len(self.planets)):
                cm += self.planets[i].pos
                m_tot += self.planets[i].mass
                for j in range(i+1, len(self.planets)):
                    self.collision(self.planets[i], self.planets[j])
            for i in range(len(self.planets)):
                self.planets[i].update(accelerations[i], painter)
            cm = cm / m_tot
            #print(np.linalg.norm(self.cm - cm))
            self.cm = cm
            painter.setBrush(Qt.red)
            try:
                painter.drawEllipse(QPointF(*self.camera.project(self.cm)), 5, 5)
            except(TypeError):
                pass
            painter.end()
            self.view.setPixmap(self.pixmap)

        def collision(self, p1, p2):
            n = p2.pos - p1.pos
            n_mag = np.linalg.norm(n)
            if n_mag == 0:
                return
            elif n_mag <= p1.radius + p2.radius:
                app.exit()
                print("true")
                n_hat = n / n_mag
                rel_vel = p2.vel - p1.vel
                if np.dot(rel_vel, n_hat) < 0:
                    return
                penetration = p1.radius + p2.radius - n_mag
                offset = n_hat * 0.5 * penetration
                p1.pos -= offset
                p2.pos += offset
                v1_ni = p1.vel @ n_hat
                v2_ni = p2.vel @ n_hat
                v1_nf = ((p1.mass - p2.mass) * v1_ni + 2 * v2_ni * p2.mass) / (p1.mass + p2.mass)
                v2_nf = ((p2.mass - p1.mass) * v2_ni + 2 * v1_ni * p1.mass) / (p2.mass + p1.mass)

                p1.vel += (v1_nf - v1_ni)
                p2.vel += (v2_nf - v2_ni)

        class Camera():
            def __init__(self, window, v):
                self.window = window
                self.move = {
                    Qt.Key_W: np.array([0, 0, v], dtype=float),
                    Qt.Key_A: np.array([-v, 0, 0], dtype=float),
                    Qt.Key_S: np.array([0, 0, -v], dtype=float),
                    Qt.Key_D: np.array([v, 0, 0], dtype=float),
                    Qt.Key_Control: np.array([0, v, 0], dtype=float),
                    Qt.Key_Space: np.array([0, -v, 0], dtype=float)
                }
                self.pos = np.array([0, 0, -100], dtype=float)
                self.focus = False
                self.centering = False
                self.v = np.array([0, 0, 0], dtype=float)
                self.f = np.array([0, 0, 1])
                self.u:np.ndarray
                self.r:np.ndarray
                self.get_directions()

            def get_directions(self):
                self.f = self.f / np.linalg.norm(self.f)
                world_up = np.array([1, 0, 0])
                if np.abs(self.f @ world_up) > 0.99:
                    world_up = np.array([0, 1, 0])
                self.r = np.cross(self.f, world_up)
                self.r = self.r / np.linalg.norm(self.r)
                self.u = np.cross(self.r, self.f)
                self.u = self.u / np.linalg.norm(self.u)

            def get_directional_velocity(self):
                return self.v @ np.array([self.r, self.u, self.f])
                
            def keyEvent(self, event, press):
                if event.key() == Qt.Key_Shift:
                    self.focus = True if press else False
                try:
                    self.window.camera.v += self.move[event.key()] * (1 if press else -1)
                except(KeyError):
                    return
                
            def mouseMoveEvent(self, event):
                if not self.centering:
                    self.f += (event.x() - self.window.width()/2) * self.r / focal
                    self.f += (event.y() - self.window.height()/2) * self.u / focal
                    self.get_directions()
                    self.centering = True
                    QCursor.setPos(int(self.window.width()/2), int(self.window.height()/2))
                self.centering = False

            def update(self):
                self.pos += (self.get_directional_velocity() * (0.1 if self.focus else 1))

            def get_dist(self, pos):
                return np.linalg.norm(pos - self.pos)
                
            def project_planet(self, planet):
                rel_dist = (planet.pos - self.pos)
                x_rel = rel_dist @ self.r
                y_rel = rel_dist @ self.u
                z_rel = rel_dist @ self.f
                if z_rel <= 0:
                    return None, None
                
                x_cam = x_rel * focal / z_rel
                y_cam = y_rel * focal / z_rel
                return np.array([x_cam + self.window.width()/2, y_cam + self.window.height()/2]), planet.radius * focal / z_rel
            
            def project(self, pos):
                rel_dist = pos - self.pos
                x_rel = rel_dist @ self.r
                y_rel = rel_dist @ self.u
                z_rel = rel_dist @ self.f

                if z_rel <= 0:
                    return None
                
                return np.array([x_rel * focal / z_rel + self.window.width()/2, y_rel * focal / z_rel + self.window.height()/2])

        class Object:
            objects = []
            def __init__(self, map):
                self.pos = np.array([randint(-2000, 2000), randint(-2000, 2000), randint(-2000, 2000)], dtype=float)
                self.vel = np.array([randint(-50, 50), randint(-50, 50), randint(-50, 50)], dtype=float)
                self.mass = randint(1, 10)
                self.map = map
                self.objects.append(self)

            def getDistance(self, other):
                return np.linalg.norm(other.pos-self.pos)

        class Planet(Object):
            m_multi = 10**22
            x_multi = 10**6
            def __init__(self, map):
                super().__init__(map)
                self.radius = (self.mass * 3 / 4 / pi) ** (1/3) * 5 
                self.acc = None
                #self.trail = self.Trail(self, 300)
            
            def get_acceleration(self):
                netAcc = np.array([0, 0, 0], dtype=float)
                for object in self.objects:
                    if object != self:
                        netAcc += self.get_gravity(object)
                return netAcc
            
            def get_gravity(self, other):
                x = other.pos - self.pos
                x_mag = np.linalg.norm(x)
                x_hat = x / x_mag
                return (0.001 * (other.mass * self.m_multi) / (x_mag * self.x_multi)**2) * x_hat
            
            def get_optimal_velocity(self):
                pass

            def draw3D(self, painter:QPainter=None):
                pos, rad = self.map.camera.project_planet(self)
                if type(pos) == np.ndarray:
                    rad = rad * 10
                    acc_pos = self.map.camera.project(self.pos + self.acc * 100)
                    if type(acc_pos) == np.ndarray:
                        painter.setPen(Qt.white)
                        painter.drawLine(QPointF(*pos), QPointF(*(acc_pos)))
                    shadow = self.get_shadow(pos, rad)
                    #painter.setBrush(shadow if type(shadow) == QRadialGradient else Qt.yellow)
                    painter.setBrush(shadow)
                    painter.setPen(Qt.transparent)
                    painter.drawEllipse(QPointF(*pos), rad, rad)
                    # painter.setPen(Qt.red)
                    # if shadow and type(shadow[0]) == np.ndarray and type(shadow[1]) == np.ndarray:
                    #     painter.drawLine(QPointF(*shadow[0]), QPointF(*shadow[1]))

            def get_shadow(self, c_pos, c_rad):
                # l_dist = self.map.light - self.pos
                # l_hat = l_dist / np.linalg.norm(l_dist)
                # l_rad = l_hat * self.radius
                
                # close_edge = self.pos + l_rad
                # far_edge = self.pos - l_rad

                # close_dist = np.linalg.norm(close_edge - self.map.camera.pos)
                # far_dist = np.linalg.norm(far_edge - self.map.camera.pos)

                # if close_dist < far_dist:
                #     close_edge_pos = self.map.camera.project(close_edge)
                #     if type(close_edge_pos) == np.ndarray:
                #         gradient = QRadialGradient(QPointF(*c_pos), c_rad * pi, QPointF(*close_edge_pos))
                #         gradient.setColorAt(0.0, Qt.yellow)
                #         gradient.setColorAt(0.4, Qt.black)

                #         return gradient

                # else:
                #     far_edge_pos = self.map.camera.project(far_edge)
                #     if type(far_edge_pos) == np.ndarray:
                #         gradient = QRadialGradient(QPointF(*c_pos), c_rad * pi, QPointF(*far_edge_pos))
                #         gradient.setColorAt(0.4, Qt.white)
                #         gradient.setColorAt(0.2, Qt.black)
                        
                #         return gradient
                # return None
                dist = np.linalg.norm(self.map.camera.pos - self.pos)
                norm_dist = -255 / (1 + 5 ** -((dist-3000)/3000)) + 255
                return QColor(0, int(norm_dist), 0, 255)


            def update(self, new_acc, painter):
                self.pos += self.vel * dt + 0.5 * self.acc * dt**2
                self.vel += 0.5 * (self.acc + new_acc) * dt
                self.acc = new_acc
                #self.trail.update(self.map.camera, painter)
                self.draw3D(painter)

            class Trail:
                def __init__(self, planet, cap):
                    self.planet = planet
                    self.points = [planet.pos]
                    self.cap = cap

                def update(self, camera, painter):
                    self.points.append(self.planet.pos)
                    if (len(self.points) > self.cap):
                        for i in range(len(self.points) - self.cap):
                            self.points.pop(i)
                    self.draw(camera, painter)
                
                def draw(self, camera, painter:QPainter):
                    painter.setBrush(Qt.transparent)
                    painter.setPen(Qt.white)
                    for i in range(len(self.points) - 1):
                        pos1 = camera.project(self.points[i])
                        pos2 = camera.project(self.points[i+1])
                        if (type(pos1) == np.ndarray and type(pos2) == np.ndarray):
                            painter.drawLine(QPointF(*pos1), QPointF(*pos2))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    focal = app.primaryScreen().size().width()/2
    w = MainWindow(app.primaryScreen().size())
    w.show()
    sys.exit(app.exec())
