import numpy as np
import scipy.io as sio
import scipy.sparse as sps

from django.db import connection

from phidb.db.backends.postgresql_psycopg2.base import *
import django_utils.config as c


OUTFILE = "experiment1_control_matrices.mat"

def x_generation_sql():
    with server_side_cursors(connection):
        cursor = connection.cursor()

        sql_query = """
        SELECT route_split_od
        FROM agent_trajectory_experiment
        ORDER BY orig, dest, waypoints, route_choice
        """
        cursor.execute(sql_query)
        return np.squeeze(np.array([row for row in cursor]))

def f_generation_sql():
    with server_side_cursors(connection):
        cursor = connection.cursor()

        sql_query = """
        SELECT sum(route_value)
        FROM agent_trajectory_experiment
        GROUP BY orig, dest
        ORDER BY orig, dest
        """
        cursor.execute(sql_query)
        return np.squeeze(np.array([row for row in cursor]))

def U_generation_sql():
    with server_side_cursors(connection):
        cursor = connection.cursor()

        sql_query = """
        SELECT count(id)
        FROM agent_trajectory_experiment
        GROUP BY orig, dest
        ORDER BY orig, dest
        """
        cursor.execute(sql_query)
        block_sizes = np.squeeze(np.array([row for row in cursor]))
    return block_sizes_to_U(block_sizes)

def block_sizes_to_U(block_sizes):
    cum_bs = np.cumsum(block_sizes)
    total = np.sum(block_sizes)
    blocks = []
    for i in block_sizes:
        blocks.append(1)
        if i > 1:
            for j in range(i-1):
                blocks.append(0)
    I = np.cumsum(blocks)-1 
    J = np.array(range(total))
    V = np.ones(total)
    return sps.csr_matrix((V,(I,J)))

def A_generation_sql(phi):
    with server_side_cursors(connection):
        cursor = connection.cursor()

        sql_query = """
        SELECT b.matrix_id AS orig, c.matrix_id AS dest, a.route_choice
        FROM agent_trajectory_experiment a, orm_matrixtaz b, orm_matrixtaz c
        WHERE a.orig = b.taz_id AND a.dest = c.taz_id
        ORDER BY a.orig, a.dest, a.waypoints, a.route_choice
        """
        cursor.execute(sql_query)
        indices = [row for row in cursor]
    I,J,V = [],[],[]
    for i,(o,d,r) in enumerate(indices):
        route_to_links = phi[(o,d)][r]
        size = len(route_to_links)
        I.extend(route_to_links)
        J.extend([i]*size)
        V.extend([1]*size)
    return sps.csr_matrix((V,(I,J)),shape=(1033,len(indices)))

if __name__ == "__main__":
#def run_experiment1_control():
    #phi = generate_phi.phi_generation_sql(2)
    x = x_generation_sql()
    U = U_generation_sql()
    f = f_generation_sql()

    assert(np.sum(U.dot(x)) == U.shape[0])

    f = U.T.dot(f)
    size = f.shape[0]
    F = sps.dia_matrix(([f],[0]),shape=(size,size))

    sub_phi = A_generation_sql(phi)
    A = sub_phi.dot(F)
    b = A.dot(x)

    sio.savemat('%s/%s/%s' % (c.DATA_DIR,c.EXPERIMENT_MATRICES_DIR, OUTFILE),
            {'A':A, 'U':U, 'x':x, 'b':b, 'f':f})
