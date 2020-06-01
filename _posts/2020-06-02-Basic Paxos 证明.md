---
layout: post
title: "Basic Paxos 证明"
---
Paxos是Leslie Lamport为解决集群各个节点共识提出的算法。其中最重要和最基础的是Basic Paxos。
首先给出伪代码简单说明整个Basic的算法细节。接下来接需要证明Basic Paxos确实能够保证使集群达成共识。

## Basic Paxos算法展示

伪代码，参考[1],这里省去[1]中的instance，只列出在同一instance下，如何达成共识。

Proposer 的逻辑

```c++
Proposer::Run(value V) {
    proposalN = ChooseN();   //选择一个唯一且比见过的都大的N值
    //调用集群中每一个节点的acceptor::prepare 接口。
    //包括自己的（Proposer 自己也要接受自己的提议。这时，自己也是accpotor）
    for (acceptor :  ALL) {
        //phase 1
        prepare_results.push_back(acceptor.Prepare(proposalN));
    }
    if Quorums(prepare_results) {
        //如果过收获了法定数（> ALL / 2）的prepare_ok.
        //将v`置为返回中最大n_a的v_a,如果v`都没有的话等于入参V
        v` = FindMaxNa(results);
        if (v` == null) {
            v` = V;
        }
        for (acceptor : ALL) {
            //phase 2
            accept_results.push_back(acceptor.Accept(proposalN, v`))
        }
        //  如果法定人数的acceptor Accept了提议，那么就意味着达成共识。进行commit
        if Quorums(accept_results) {
            for (acceptor : ALL) {
                //phase 3
                acceptor.Decide(v`)
            }
        }
    }
}
```

Acceptor 的逻辑

```c++
Acceptor {
    HightN = 0; //目前见到的最大的n
    AcceptN = 0;//当前接受V的N值
    AcceptV = null; //当前接受的V值

    (is_ok, n_a, n_v) Acceptor::Prepare(proposalN) {
        if (proposalN > HightN) {
            HightN = proposalN;
            return true, AcceptN, AcceptV
        }
        return false, null, null
    }

    (is_ok) Acceptor::Accept(proposalN, V) {
        if (proposalN >= HightN) {
            HightN = proposalN;
            AcceptN = proposalN;
            AcceptV = V;
            return true;
        }
        return false;
    }

    void Acceptor::Decide(V) {
        paxos_commit(V);
    }
};
```

Paxos中最精彩和关键的就是某个提案被大多数acceptor**被选定**了，那么这个提案就是共识的提案了。

证明过程参考[2]
定义：

1. 提案proposal(N, v) **被接受**，即至少有一个acceptor接受了这个proposal(N, v)。
2. 提案proposal(N, v) **被选定**，即proposal(N, v)被有符合法定节点个数（大于总节点的1/2）的节点接受。

用数学的语言描述就是“*某个提案被大多数acceptor选定了，那么这个提案就是共识的提案了*”就是：

任意两个**被选定**的提案proposal(M, U)，proposal(M`, W)。 那么U一定等于W。

下面为证明过程：

当$$M'\gt M$$ 时，假设$$U\neq W$$。

设当$$N \gt M$$，提案proposal(N, V) 为提案proposal(M, U)后$$N$$值最小的且$$V\neq U$$值的被接受的提案【\*】。那么在$$N > K \geq M$$时，提案proposal(K, value) 的value $$= U$$【\*\*】。

 - 因为提案proposal(M, U)被选定，那么proposal(M, U)必然被法定人数的节点所接受。设接受这个proposal(M, U)的集合为$$M_1$$.
  
 - 又因为提案proposal(N, V)被接受，proposer在prepare阶段获得了法定人数的同意，设这个法定人数同意的集合为$$M_2$$，且$$M_2$$中至少有一个节点返回了(true, K, value=V)给proposer。


那么$$\forall q \in M_1\cap M_2$$
 - 因为$$q\in M_1$$,那么$$q$$接受了proposal(M, U)。

 - 又因为$$q\in M_2$$, 那么$$q$$给proposer发送了(K, value)。

因为 $$N > M$$, 所以$$q$$在返回给proposer (true, K, value)时已经接受了proposal(M, U)。
又因为$$N > K \geq M$$， 所以proposer 从包含有(true, K, U)的返回中选择出了$$V$$。

设返回给proposer的值(true, J, value), 且 $$J < N$$:

1. 如果$$J < K$$, 那么proposer不可能选(J, value), 因为算法规定 **将v`置为返回中最大n_a的v_a**
2. 如果 $$N > J \geq K$$, 那么proposer选择(J, value)，又因为 $$N > J \geq M$$, (J, value)中value = $$U$$【\*\*】; 与假设的U $$\neq$$ V矛盾【\*】。

所以$$N > M$$时 $$U = V$$， 又因为 $$M' > M$$ , 对应的$$W$$也等于$$U$$。


[1] [https://pdos.csail.mit.edu/archive/6.824-2012/labs/lab-6.html](https://pdos.csail.mit.edu/archive/6.824-2012/labs/lab-6.html)

[2] [http://www.cs.toronto.edu/~samvas/teaching/2415/handouts/paxos-proof.pdf](http://www.cs.toronto.edu/~samvas/teaching/2415/handouts/paxos-proof.pdf)