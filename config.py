c = get_config()  # @UndefinedVariable

c.DataFlow.maxelements = 42
c.DataFlow.log_level = 'DEBUG'
c.DataFlow.nodelist = [
    ('SOURCE', 'dafl.examples.nodes.NumberGenerator'),
    ('SINK', 'dafl.examples.nodes.NumberWriter')
]
c.DataFlow.targets_per_node = {'SOURCE': ['SINK', ]}
c.DataFlow.maxitterations = 20

c.BulletinBoardClient.prefix = u'backend'
#c.BulletinBoardClient.postfix = str(rank)

c.aliases = dict(maxitterations='DataFlow.maxitterations',
                 start='NumberGenerator.start',
                 stop='NumberGenerator.stop')


